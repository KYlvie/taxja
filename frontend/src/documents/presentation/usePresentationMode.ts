import { useCallback, useEffect, useRef, useState } from 'react';
import type { DocumentPresentationMode } from './types';

export const usePresentationMode = (
  initialMode: DocumentPresentationMode,
  identityKey: string
) => {
  const [mode, setMode] = useState<DocumentPresentationMode>(initialMode);
  const [isUserControlled, setIsUserControlled] = useState(false);
  const previousIdentityKey = useRef(identityKey);

  useEffect(() => {
    if (previousIdentityKey.current !== identityKey) {
      previousIdentityKey.current = identityKey;
      setMode(initialMode);
      setIsUserControlled(false);
      return;
    }

    if (!isUserControlled) {
      setMode(initialMode);
    }
  }, [identityKey, initialMode, isUserControlled]);

  const setUserMode = useCallback((nextMode: DocumentPresentationMode) => {
    setMode(nextMode);
    setIsUserControlled(true);
  }, []);

  const resetModeFromServer = useCallback(() => {
    setMode(initialMode);
    setIsUserControlled(false);
  }, [initialMode]);

  return {
    mode,
    setMode: setUserMode,
    resetModeFromServer,
    isUserControlled,
  };
};

export default usePresentationMode;
