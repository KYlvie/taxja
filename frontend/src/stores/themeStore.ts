import { create } from 'zustand';
import { persist } from 'zustand/middleware';

type Theme = 'classic' | 'cyber';

interface ThemeState {
  theme: Theme;
  toggleTheme: () => void;
}

const applyTheme = (theme: Theme) => {
  if (theme === 'cyber') {
    document.documentElement.setAttribute('data-theme', 'cyber');
  } else {
    document.documentElement.removeAttribute('data-theme');
  }
};

export const useThemeStore = create<ThemeState>()(
  persist(
    (set, get) => ({
      theme: 'classic',
      toggleTheme: () => {
        const next = get().theme === 'classic' ? 'cyber' : 'classic';
        applyTheme(next);
        set({ theme: next });
      },
    }),
    {
      name: 'taxja-theme',
      onRehydrateStorage: () => (state) => {
        if (state?.theme) applyTheme(state.theme);
      },
    }
  )
);
