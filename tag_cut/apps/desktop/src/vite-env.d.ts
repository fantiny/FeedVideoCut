export {}

declare global {
  interface Window {
    tagCut?: {
      apiBase: string
      onBackendStatus?: (callback: (payload: { ok?: boolean; logs?: string[] }) => void) => () => void
      pickDirectory?: () => Promise<string | null>
    }
  }
}
