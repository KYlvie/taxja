/// <reference types="vite/client" />

interface ImportMetaEnv {
  readonly VITE_API_URL?: string
  readonly VITE_API_BASE_URL?: string
  readonly VITE_MOBILE_API_BASE_URL?: string
  readonly VITE_ENV?: string
  readonly VITE_DOCUMENT_PRESENTATION_RESOLVER_V1?: string
}

interface ImportMeta {
  readonly env: ImportMetaEnv
}
