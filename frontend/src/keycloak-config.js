export const keycloakConfig = {
  url: `http://${process.env.APP_HOST}:${process.env.KEYCLOAK_PORT}`,
  realm: 'ceia',
  clientId: 'chatbot-frontend',
};

export const keycloakInitOptions = {
  onLoad: 'login-required',
  checkLoginIframe: false,
  redirectUri: window.location.origin + window.location.pathname,
};