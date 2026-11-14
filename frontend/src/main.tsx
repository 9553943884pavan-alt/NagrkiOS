import React from 'react';import {createRoot} from 'react-dom/client';
import {BrowserRouter} from 'react-router-dom';import {AuthProvider} from './context/AuthContext';
import App from './App';import './styles.css';
// Show a subtle focus ring for keyboard navigation, not mouse clicks inside text fields.
document.documentElement.dataset.inputMode='pointer';
document.addEventListener('pointerdown',()=>{document.documentElement.dataset.inputMode='pointer';},true);
document.addEventListener('keydown',event=>{if(['Tab','ArrowUp','ArrowDown','ArrowLeft','ArrowRight','Home','End'].includes(event.key))document.documentElement.dataset.inputMode='keyboard';},true);
createRoot(document.getElementById('root')!).render(<React.StrictMode><BrowserRouter><AuthProvider><App/></AuthProvider></BrowserRouter></React.StrictMode>);
