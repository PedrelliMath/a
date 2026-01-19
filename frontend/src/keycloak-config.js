export const keycloakConfig = {
  url: 'http://localhost:8080',
  realm: 'ceia',
  clientId: 'chatbot-frontend',
};

export const keycloakInitOptions = {
  onLoad: 'login-required',
  checkLoginIframe: false,
  pkceMethod: 'S256',
};