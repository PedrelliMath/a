// Runtime configuration for Keycloak - No rebuild needed
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
