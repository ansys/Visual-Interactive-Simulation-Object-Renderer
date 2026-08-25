import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import App from './App';
import './styles/index.css';
import './styles/inputs.css';
import './styles/themes/visor-theme-rules.css';

createRoot(document.getElementById('VisorContainer')!).render(
    <StrictMode>
        <App />
    </StrictMode>
);
