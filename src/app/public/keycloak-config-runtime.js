// Runtime configuration for Keycloak and API - No rebuild needed
window.KEYCLOAK_CONFIG = {
  url: 'http://200.137.197.134:18080',
  realm: 'ceia',
  clientId: 'chatbot-frontend',
};

window.KEYCLOAK_INIT_OPTIONS = {
  onLoad: 'login-required',
  checkLoginIframe: false,
  redirectUri: window.location.origin + window.location.pathname,
};

// API Configuration
window.API_CONFIG = {
  baseURL: 'http://localhost:8000'
};
