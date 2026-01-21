export const keycloakConfig = {
  url: 'http://100.67.134.67:8080',
  realm: 'ceia',
  clientId: 'chatbot-frontend',
};

export const keycloakInitOptions = {
  onLoad: 'login-required',
  checkLoginIframe: false,
  pkceMethod: 'S256',
};