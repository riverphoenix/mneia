from __future__ import annotations

import asyncio
import logging
import platform
import subprocess
import tempfile
from pathlib import Path

logger = logging.getLogger(__name__)

SAMPLE_RATE = 16000
CHANNELS = 1


def is_available() -> bool:
    if platform.system() != "Darwin":
        return False
    try:
        version = platform.mac_ver()[0]
        major = int(version.split(".")[0])
        return major >= 13
    except Exception:
        return False


def _find_sck_binary() -> Path | None:
    sck_dir = Path(__file__).parent.parent / "bin"
    binary = sck_dir / "mneia-audio-capture"
    if binary.exists() and binary.stat().st_mode & 0o111:
        return binary
    return None


_SCK_SWIFT_SOURCE = '''\
import AVFoundation
import Foundation
import ScreenCaptureKit

@available(macOS 13.0, *)
class AudioCapturer: NSObject, SCStreamDelegate, SCStreamOutput {
    var stream: SCStream?
    var outputFile: AVAudioFile?
    var outputPath: String
    var duration: Double
    var sampleRate: Double
    let semaphore = DispatchSemaphore(value: 0)

    init(outputPath: String, duration: Double, sampleRate: Double) {
        self.outputPath = outputPath
        self.duration = duration
        self.sampleRate = sampleRate
    }

    func start() async throws {
        let content = try await SCShareableContent.excludingDesktopWindows(
            false, onScreenWindowsOnly: false
        )
        guard let display = content.displays.first else {
            fputs("No display found\\n", stderr)
            exit(1)
        }

        let filter = SCContentFilter(display: display, excludingWindows: [])
        let config = SCStreamConfiguration()
        config.capturesAudio = true
        config.excludesCurrentProcessAudio = true
        config.sampleRate = Int(sampleRate)
        config.channelCount = 1

        config.width = 1
        config.height = 1
        config.minimumFrameInterval = CMTime(value: 1, timescale: 1)
        config.showsCursor = false

        let format = AVAudioFormat(
            commonFormat: .pcmFormatInt16,
            sampleRate: sampleRate,
            channels: 1,
            interleaved: true
        )!

        let url = URL(fileURLWithPath: outputPath)
        let wavSettings: [String: Any] = [
            AVFormatIDKey: Int(kAudioFormatLinearPCM),
            AVSampleRateKey: sampleRate,
            AVNumberOfChannelsKey: 1,
            AVLinearPCMBitDepthKey: 16,
            AVLinearPCMIsFloatKey: false,
            AVLinearPCMIsBigEndianKey: false,
        ]
        outputFile = try AVAudioFile(
            forWriting: url,
            settings: wavSettings,
            commonFormat: .pcmFormatInt16,
            interleaved: true
        )

        stream = SCStream(filter: filter, configuration: config, delegate: self)
        try stream!.addStreamOutput(self, type: .audio, sampleHandlerQueue: .main)
        try await stream!.startCapture()

        DispatchQueue.main.asyncAfter(deadline: .now() + duration) {
            Task {
                try? await self.stream?.stopCapture()
                self.outputFile = nil
                self.semaphore.signal()
            }
        }

        semaphore.wait()
    }

    func stream(
        _ stream: SCStream,
        didOutputSampleBuffer sampleBuffer: CMSampleBuffer,
        of type: SCStreamOutputType
    ) {
        guard type == .audio, let file = outputFile else { return }
        guard let formatDesc = sampleBuffer.formatDescription else { return }
        let audioFormat = AVAudioFormat(cmAudioFormatDescription: formatDesc)
        guard let pcmBuffer = AVAudioPCMBuffer(
            pcmFormat: audioFormat,
            frameCapacity: AVAudioFrameCount(
                sampleBuffer.numSamples
            )
        ) else { return }
        pcmBuffer.frameLength = AVAudioFrameCount(sampleBuffer.numSamples)

        let status = CMSampleBufferCopyPCMDataIntoAudioBufferList(
            sampleBuffer,
            at: 0,
            frameCount: Int32(sampleBuffer.numSamples),
            into: pcmBuffer.mutableAudioBufferList
        )
        guard status == noErr else { return }

        try? file.write(from: pcmBuffer)
    }

    func stream(_ stream: SCStream, didStopWithError error: Error) {
        fputs("Stream error: \\(error)\\n", stderr)
        semaphore.signal()
    }
}

if #available(macOS 13.0, *) {
    let args = CommandLine.arguments
    let outputPath = args.count > 1 ? args[1] : "/tmp/mneia-audio.wav"
    let duration = args.count > 2 ? Double(args[2]) ?? 30.0 : 30.0
    let sampleRate = args.count > 3 ? Double(args[3]) ?? 16000.0 : 16000.0

    let capturer = AudioCapturer(
        outputPath: outputPath,
        duration: duration,
        sampleRate: sampleRate
    )
    let semaphore = DispatchSemaphore(value: 0)
    Task {
        do {
            try await capturer.start()
        } catch {
            fputs("Capture error: \\(error)\\n", stderr)
        }
        semaphore.signal()
    }
    semaphore.wait()
} else {
    fputs("Requires macOS 13+\\n", stderr)
    exit(1)
}
'''


def compile_capture_binary() -> Path | None:
    existing = _find_sck_binary()
    if existing:
        return existing

    bin_dir = Path(__file__).parent.parent / "bin"
    bin_dir.mkdir(parents=True, exist_ok=True)
    binary = bin_dir / "mneia-audio-capture"

    with tempfile.NamedTemporaryFile(
        suffix=".swift", mode="w", delete=False,
    ) as f:
        f.write(_SCK_SWIFT_SOURCE)
        swift_path = f.name

    try:
        result = subprocess.run(
            [
                "swiftc",
                "-O",
                "-framework", "ScreenCaptureKit",
                "-framework", "AVFoundation",
                "-framework", "CoreMedia",
                swift_path,
                "-o", str(binary),
            ],
            capture_output=True,
            text=True,
            timeout=120,
        )
        if result.returncode != 0:
            logger.error(f"Swift compilation failed: {result.stderr}")
            return None
        return binary
    except FileNotFoundError:
        logger.error(
            "swiftc not found. Install Xcode Command Line Tools: "
            "xcode-select --install"
        )
        return None
    except Exception as e:
        logger.error(f"Compilation failed: {e}")
        return None
    finally:
        Path(swift_path).unlink(missing_ok=True)


async def record_system_audio(
    output_path: Path,
    duration_seconds: int = 30,
    sample_rate: int = SAMPLE_RATE,
) -> bool:
    binary = _find_sck_binary() or compile_capture_binary()
    if not binary:
        return False

    try:
        proc = await asyncio.create_subprocess_exec(
            str(binary),
            str(output_path),
            str(duration_seconds),
            str(sample_rate),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        _, stderr = await asyncio.wait_for(
            proc.communicate(),
            timeout=duration_seconds + 30,
        )
        if proc.returncode != 0:
            logger.error(
                f"Audio capture failed: {stderr.decode().strip()}"
            )
            return False
        return output_path.exists() and output_path.stat().st_size > 0
    except asyncio.TimeoutError:
        proc.kill()
        logger.error("Audio capture timed out")
        return False
    except Exception as e:
        logger.error(f"Audio capture error: {e}")
        return False
