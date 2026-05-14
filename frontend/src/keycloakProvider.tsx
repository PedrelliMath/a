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
    // Use runtime config if available, otherwise fall back to build-time config
    const runtimeConfig = (window as any).KEYCLOAK_CONFIG || keycloakConfig;
    const runtimeInitOptions = (window as any).KEYCLOAK_INIT_OPTIONS || keycloakInitOptions;
    
    console.log('🔧 Keycloak Config:', runtimeConfig);
    
    const kc = new Keycloak(runtimeConfig);

    kc.init(runtimeInitOptions)
      .then((authenticated) => {
        console.log('🔐 Keycloak inicializado. Authenticated:', authenticated);
        
        setKeycloak(kc);
        setAuthenticated(authenticated);
        setLoading(false);

        if (authenticated) {
          kc.onTokenExpired = () => {
            console.log('⏰ Token expirado, renovando...');
            kc.updateToken(30)
              .then((refreshed) => {
                if (refreshed) {
                  console.log('✅ Token renovado com sucesso');
                } else {
                  console.log('ℹ️ Token ainda válido');
                }
              })
              .catch(() => {
                console.log('❌ Falha ao renovar token, redirecionando para login');
                kc.login();
              });
          };
        }
      })
      .catch((error) => {
        console.error('❌ Erro ao inicializar Keycloak:', error);
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
          <div className="inline-block animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600 mb-4"></div>
          <h2 className="text-xl font-bold text-gray-800 mb-2">Redirecionando para login...</h2>
          <p className="text-sm text-gray-600">Você será redirecionado em instantes</p>
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