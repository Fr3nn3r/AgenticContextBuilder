import React from 'react'
import ReactDOM from 'react-dom/client'
import { BrowserRouter } from 'react-router-dom'
import { ViteThemeProvider } from '@space-man/react-theme-animation'
import App from './App'
import './index.css'

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <ViteThemeProvider
      defaultTheme="system"
      storageKey="cb-theme"
      attribute="class"
      colorThemes={['northern-lights', 'default', 'pink']}
      defaultColorTheme="northern-lights"
    >
      <BrowserRouter>
        <App />
      </BrowserRouter>
    </ViteThemeProvider>
  </React.StrictMode>,
)
