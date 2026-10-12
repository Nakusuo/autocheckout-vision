import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import '@fontsource/overpass/latin-600.css'
import '@fontsource/overpass/latin-800.css'
import '@fontsource/overpass/latin-900.css'
import './tokens.css'
import App from './App.tsx'

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <App />
  </StrictMode>,
)
