import React, { createContext, useContext, useState, useEffect } from 'react';
import Keycloak from 'keycloak-js';
import { keycloakConfig, keycloakInitOptions } from './keycloak-config.js';

const KeycloakContext = createContext(null);

export const useKeycloak = () => {
  const context = useContext(KeycloakContext);
  if (!context) {
    throw new Error('useKeycloak must be used within KeycloakProvider');
  }
  return context;
};

export const KeycloakProvider = ({ children }) => {
  const [keycloak, setKeycloak] = useState(null);
  const [authenticated, setAuthenticated] = useState(false);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const kc = new Keycloak(keycloakConfig);
    
    kc.init(keycloakInitOptions)
      .then((authenticated) => {
        setKeycloak(kc);
        setAuthenticated(authenticated);
        setLoading(false);
        
        // Auto-refresh do token
        kc.onTokenExpired = () => {
          kc.updateToken(30).catch(() => kc.login());
        };
      })
      .catch((error) => {
        console.error('Erro ao inicializar Keycloak:', error);
        setLoading(false);
      });
  }, []);

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-screen bg-gray-50">
        <div className="text-center">
          <div className="inline-block animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600 mb-4"></div>
          <p className="text-gray-600">Autenticando...</p>
        </div>
      </div>
    );
  }

  if (!authenticated) {
    return (
      <div className="flex items-center justify-center min-h-screen bg-gray-50">
        <div className="text-center">
          <h2 className="text-2xl font-bold text-gray-800 mb-4">Redirecionando para login...</h2>
        </div>
      </div>
    );
  }

  return (
    <KeycloakContext.Provider
      value={{
        keycloak,
        authenticated,
        logout: () => keycloak.logout(),
        getToken: () => keycloak.token,
        getUserInfo: () => keycloak.tokenParsed,
      }}
    >
      {children}
    </KeycloakContext.Provider>
  );
};