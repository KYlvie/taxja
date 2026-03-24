interface GoogleCredentialResponse {
  credential?: string;
  select_by?: string;
}

interface GoogleAccountsIdConfiguration {
  client_id: string;
  callback: (response: GoogleCredentialResponse) => void;
  ux_mode?: 'popup' | 'redirect';
  context?: 'signin' | 'signup' | 'use';
  auto_select?: boolean;
  cancel_on_tap_outside?: boolean;
}

interface GoogleAccountsIdButtonConfiguration {
  type?: 'standard' | 'icon';
  theme?: 'outline' | 'filled_blue' | 'filled_black';
  size?: 'large' | 'medium' | 'small';
  text?: 'signin_with' | 'signup_with' | 'continue_with' | 'signin';
  shape?: 'rectangular' | 'pill' | 'circle' | 'square';
  logo_alignment?: 'left' | 'center';
  width?: number;
  locale?: string;
}

interface GoogleAccountsIdApi {
  initialize: (configuration: GoogleAccountsIdConfiguration) => void;
  renderButton: (
    parent: HTMLElement,
    options: GoogleAccountsIdButtonConfiguration,
  ) => void;
}

interface Window {
  google?: {
    accounts: {
      id: GoogleAccountsIdApi;
    };
  };
}
