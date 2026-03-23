export const isDocumentPresentationResolverEnabled = (): boolean => {
  const explicitFlag = import.meta.env.VITE_DOCUMENT_PRESENTATION_RESOLVER_V1;
  if (explicitFlag != null) {
    return explicitFlag === 'true';
  }

  return Boolean(import.meta.env.DEV);
};

export default isDocumentPresentationResolverEnabled;
