import React from 'react'
import ReactDOM from 'react-dom/client'
import { BrowserRouter } from 'react-router-dom'
import { SpacemanThemeProvider, ThemeAnimationType } from '@space-man/react-theme-animation'
import { AuthProvider } from './context/AuthContext'
import { FilterProvider } from './context/FilterContext'
import { BatchProvider } from './context/BatchContext'
import { ClaimsProvider } from './context/ClaimsContext'
import { HelpTooltipProvider } from './components/shared'
import App from './App'
import './index.css'

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <SpacemanThemeProvider
      defaultTheme="system"
      defaultColorTheme="northern-lights"
      themes={['light', 'dark', 'system']}
      colorThemes={['northern-lights', 'default', 'pink', 'modern-minimal', 'ocean-breeze', 'clean-slate']}
      animationType={ThemeAnimationType.CIRCLE}
      duration={500}
    >
      <BrowserRouter>
        <AuthProvider>
          <BatchProvider>
            <FilterProvider>
              <ClaimsProvider>
                <HelpTooltipProvider>
                  <App />
                </HelpTooltipProvider>
              </ClaimsProvider>
            </FilterProvider>
          </BatchProvider>
        </AuthProvider>
      </BrowserRouter>
    </SpacemanThemeProvider>
  </React.StrictMode>,
)
