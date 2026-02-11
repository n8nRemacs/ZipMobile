declare global {
  interface Window {
    Telegram?: {
      WebApp: {
        initData: string
        initDataUnsafe: {
          user?: {
            id: number
            first_name: string
            last_name?: string
            username?: string
          }
          auth_date: number
          hash: string
        }
        ready: () => void
        close: () => void
        expand: () => void
        requestContact: (callback: (result: any) => void) => void
        HapticFeedback: {
          impactOccurred: (style: 'light' | 'medium' | 'heavy' | 'rigid' | 'soft') => void
          notificationOccurred: (type: 'error' | 'success' | 'warning') => void
        }
        themeParams: Record<string, string>
        colorScheme: 'light' | 'dark'
        isExpanded: boolean
        viewportHeight: number
        viewportStableHeight: number
      }
    }
  }
}

export interface TelegramContact {
  phone_number: string
  first_name: string
  last_name?: string
  user_id: number
}

export function useTelegram() {
  const webApp = window.Telegram?.WebApp

  function getInitData(): string {
    return webApp?.initData || ''
  }

  function getUserInfo() {
    return webApp?.initDataUnsafe?.user || null
  }

  /**
   * Request contact via Telegram WebApp.
   * Handles both Bot API 7.2+ ({status, responseUnsafe}) and older ({status: bool}) formats.
   */
  function requestContact(): Promise<TelegramContact> {
    return new Promise((resolve, reject) => {
      if (!webApp) {
        reject(new Error('Telegram WebApp not available'))
        return
      }
      webApp.requestContact((result: any) => {
        console.log('[TG] requestContact result:', JSON.stringify(result))

        // Bot API 7.2+: result = { status: "sent"|"cancelled", responseUnsafe?: { contact: {...} } }
        if (result && typeof result === 'object' && 'status' in result) {
          if (result.status === 'sent' && result.responseUnsafe?.contact) {
            resolve(result.responseUnsafe.contact)
            return
          }
          reject(new Error(result.status === 'cancelled' ? 'Contact sharing cancelled' : 'No contact data in response'))
          return
        }

        // Older format: result = true/false (boolean)
        if (result === true) {
          reject(new Error('Contact shared but data not available in this Telegram version'))
          return
        }

        reject(new Error('Contact sharing denied'))
      })
    })
  }

  function ready() {
    webApp?.ready()
  }

  function close() {
    webApp?.close()
  }

  function expand() {
    webApp?.expand()
  }

  function hapticFeedback(type: 'success' | 'error' | 'warning') {
    webApp?.HapticFeedback?.notificationOccurred(type)
  }

  const isAvailable = !!webApp

  return {
    webApp,
    isAvailable,
    getInitData,
    getUserInfo,
    requestContact,
    ready,
    close,
    expand,
    hapticFeedback,
  }
}
