import { useRef, useState, useEffect } from 'react';
import { useTranslation } from 'react-i18next';
import './CameraCapture.css';

interface CameraCaptureProps {
  onCapture: (file: File) => void;
  onClose: () => void;
}

export const CameraCapture = ({ onCapture, onClose }: CameraCaptureProps) => {
  const { t } = useTranslation();
  const videoRef = useRef<HTMLVideoElement>(null);
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const [stream, setStream] = useState<MediaStream | null>(null);
  const [error, setError] = useState<string>('');
  const [facingMode, setFacingMode] = useState<'user' | 'environment'>('environment');
  const [hasMultipleCameras, setHasMultipleCameras] = useState(false);

  useEffect(() => {
    startCamera();
    checkMultipleCameras();

    return () => {
      stopCamera();
    };
  }, [facingMode]);

  const checkMultipleCameras = async () => {
    try {
      const devices = await navigator.mediaDevices.enumerateDevices();
      const videoDevices = devices.filter(device => device.kind === 'videoinput');
      setHasMultipleCameras(videoDevices.length > 1);
    } catch (err) {
      console.error('Error checking cameras:', err);
    }
  };

  const startCamera = async () => {
    try {
      const mediaStream = await navigator.mediaDevices.getUserMedia({
        video: {
          facingMode: facingMode,
          width: { ideal: 1920 },
          height: { ideal: 1080 }
        }
      });

      if (videoRef.current) {
        videoRef.current.srcObject = mediaStream;
      }

      setStream(mediaStream);
      setError('');
    } catch (err) {
      console.error('Error accessing camera:', err);
      setError(t('camera.error.access'));
    }
  };

  const stopCamera = () => {
    if (stream) {
      stream.getTracks().forEach(track => track.stop());
      setStream(null);
    }
  };

  const switchCamera = () => {
    stopCamera();
    setFacingMode(prev => prev === 'user' ? 'environment' : 'user');
  };

  const capturePhoto = () => {
    if (!videoRef.current || !canvasRef.current) return;

    const video = videoRef.current;
    const canvas = canvasRef.current;
    const context = canvas.getContext('2d');

    if (!context) return;

    // Set canvas dimensions to match video
    canvas.width = video.videoWidth;
    canvas.height = video.videoHeight;

    // Draw video frame to canvas
    context.drawImage(video, 0, 0, canvas.width, canvas.height);

    // Convert canvas to blob
    canvas.toBlob((blob) => {
      if (blob) {
        const file = new File([blob], `document-${Date.now()}.jpg`, {
          type: 'image/jpeg'
        });
        onCapture(file);
        stopCamera();
        onClose();
      }
    }, 'image/jpeg', 0.9);
  };

  const handleClose = () => {
    stopCamera();
    onClose();
  };

  return (
    <div className="camera-capture">
      <div className="camera-header">
        <button className="camera-close" onClick={handleClose}>
          ✕
        </button>
        <h2>{t('camera.title')}</h2>
        {hasMultipleCameras && (
          <button className="camera-switch" onClick={switchCamera}>
            🔄
          </button>
        )}
      </div>

      <div className="camera-viewport">
        {error ? (
          <div className="camera-error">
            <p>{error}</p>
            <button onClick={startCamera}>{t('camera.retry')}</button>
          </div>
        ) : (
          <>
            <video
              ref={videoRef}
              autoPlay
              playsInline
              className="camera-video"
            />
            <div className="camera-overlay">
              <div className="camera-frame" />
            </div>
          </>
        )}
      </div>

      <canvas ref={canvasRef} style={{ display: 'none' }} />

      <div className="camera-controls">
        <div className="camera-tips">
          <p>📄 {t('camera.tips.align')}</p>
          <p>💡 {t('camera.tips.lighting')}</p>
        </div>
        <button
          className="camera-capture-button"
          onClick={capturePhoto}
          disabled={!!error}
        >
          <div className="camera-capture-ring">
            <div className="camera-capture-inner" />
          </div>
        </button>
      </div>
    </div>
  );
};
