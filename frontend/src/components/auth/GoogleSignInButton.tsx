import { useEffect, useRef, useState } from 'react';
import { isNativeApp } from '../../mobile/runtime';

const GOOGLE_SCRIPT_ID = 'google-identity-services';
const GOOGLE_SCRIPT_SRC = 'https://accounts.google.com/gsi/client';

let googleScriptPromise: Promise<void> | null = null;

const loadGoogleIdentityScript = (): Promise<void> => {
  if (window.google?.accounts?.id) {
    return Promise.resolve();
  }

  if (googleScriptPromise) {
    return googleScriptPromise;
  }

  googleScriptPromise = new Promise<void>((resolve, reject) => {
    const existingScript = document.getElementById(GOOGLE_SCRIPT_ID) as HTMLScriptElement | null;
    if (existingScript) {
      if (existingScript.dataset.loaded === 'true') {
        resolve();
        return;
      }
      existingScript.addEventListener('load', () => resolve(), { once: true });
      existingScript.addEventListener('error', () => reject(new Error('Failed to load Google script')), { once: true });
      return;
    }

    const script = document.createElement('script');
    script.id = GOOGLE_SCRIPT_ID;
    script.src = GOOGLE_SCRIPT_SRC;
    script.async = true;
    script.defer = true;
    script.onload = () => {
      script.dataset.loaded = 'true';
      resolve();
    };
    script.onerror = () => reject(new Error('Failed to load Google script'));
    document.head.appendChild(script);
  });

  return googleScriptPromise;
};

interface GoogleSignInButtonProps {
  disabled?: boolean;
  label?: string;
  locale?: string;
  onCredential: (credential: string) => void;
  onError?: (code: 'google_login_unavailable' | 'google_token_invalid') => void;
}

const GoogleSignInButton = ({
  disabled = false,
  label = 'Continue with Google',
  locale,
  onCredential,
  onError,
}: GoogleSignInButtonProps) => {
  const clientId = import.meta.env.VITE_GOOGLE_CLIENT_ID?.trim();
  const containerRef = useRef<HTMLDivElement | null>(null);
  const credentialHandlerRef = useRef(onCredential);
  const errorHandlerRef = useRef(onError);
  const [isReady, setIsReady] = useState(false);

  useEffect(() => {
    credentialHandlerRef.current = onCredential;
  }, [onCredential]);

  useEffect(() => {
    errorHandlerRef.current = onError;
  }, [onError]);

  useEffect(() => {
    if (!clientId || isNativeApp()) {
      return;
    }

    let cancelled = false;

    void loadGoogleIdentityScript()
      .then(() => {
        if (cancelled || !containerRef.current || !window.google?.accounts?.id) {
          return;
        }

        const buttonHost = containerRef.current;
        buttonHost.innerHTML = '';

        window.google.accounts.id.initialize({
          client_id: clientId,
          callback: (response) => {
            if (!response.credential) {
              errorHandlerRef.current?.('google_token_invalid');
              return;
            }
            credentialHandlerRef.current(response.credential);
          },
          ux_mode: 'popup',
          context: 'signin',
          auto_select: false,
          cancel_on_tap_outside: true,
        });

        const width = Math.min(
          400,
          Math.max(240, Math.round(buttonHost.getBoundingClientRect().width || 360)),
        );

        window.google.accounts.id.renderButton(buttonHost, {
          theme: 'outline',
          size: 'large',
          shape: 'pill',
          text: 'continue_with',
          width,
          logo_alignment: 'left',
          locale,
        });

        setIsReady(true);
      })
      .catch(() => {
        if (cancelled) {
          return;
        }
        setIsReady(false);
        errorHandlerRef.current?.('google_login_unavailable');
      });

    return () => {
      cancelled = true;
      if (containerRef.current) {
        containerRef.current.innerHTML = '';
      }
    };
  }, [clientId, locale]);

  if (!clientId || isNativeApp()) {
    return null;
  }

  return (
    <div className={`google-signin-shell${disabled ? ' is-disabled' : ''}`}>
      {!isReady ? (
        <button type="button" className="btn-secondary google-signin-placeholder" disabled>
          {label}
        </button>
      ) : null}
      <div
        ref={containerRef}
        className={`google-signin-slot${isReady ? '' : ' google-signin-slot--hidden'}`}
      />
    </div>
  );
};

export default GoogleSignInButton;
