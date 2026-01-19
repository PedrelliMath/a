// auth-utils.js
import { useKeycloak } from './keycloakProvider';

export const useAuthFetch = () => {
  const { getToken } = useKeycloak();

  return async (url, options = {}) => {
    const token = getToken();
    
    const response = await fetch(url, {
      ...options,
      headers: {
        ...options.headers,
        'Authorization': `Bearer ${token}`,
      },
    });

    // Se erro 4xx ou 5xx, tenta extrair o detalhe
    if (!response.ok) {
      let errorData;
      
      try {
        errorData = await response.json();
      } catch {
        // Se não conseguir parsear JSON, usa mensagem genérica
        errorData = { 
          detail: `Erro ${response.status}: ${response.statusText}` 
        };
      }

      // Cria um objeto de erro customizado
      const error = new Error(errorData.detail || `Erro ${response.status}`);
      error.status = response.status;
      error.detail = errorData.detail || `Erro ${response.status}: ${response.statusText}`;
      error.response = errorData;
      
      throw error;
    }

    return response;
  };
};