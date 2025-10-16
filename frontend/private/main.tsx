import React from 'react';
import ReactDOM from 'react-dom/client';
import App from './App';
import '../src/style.css';
import './report.css';

const accessToken = localStorage.getItem('accessToken');

if (!accessToken) {
  window.location.href = '/';
} else {
  const rootElement = document.getElementById('root');
  if (rootElement) {
    ReactDOM.createRoot(rootElement).render(
      <React.StrictMode>
        <App />
      </React.StrictMode>,
    );
  }
}
