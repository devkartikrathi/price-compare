const API_BASE_URL = '/api';

export class ApiService {
  static async analyzeProductPrices(request: {
    product_query: string;
    user_credit_cards: string[];
    max_products_per_platform?: number;
  }) {
    const response = await fetch(`${API_BASE_URL}/analyze-prices`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(request),
    });

    if (!response.ok) {
      throw new Error(`API request failed: ${response.statusText}`);
    }

    return response.json();
  }

  static async getSupportedCards() {
    const response = await fetch(`${API_BASE_URL}/supported-cards`);
    
    if (!response.ok) {
      throw new Error(`Failed to fetch supported cards: ${response.statusText}`);
    }

    return response.json();
  }

  static async getSupportedPlatforms() {
    const response = await fetch(`${API_BASE_URL}/platforms`);
    
    if (!response.ok) {
      throw new Error(`Failed to fetch platforms: ${response.statusText}`);
    }

    return response.json();
  }

  static async healthCheck() {
    const response = await fetch(`${API_BASE_URL}/`);
    
    if (!response.ok) {
      throw new Error(`Health check failed: ${response.statusText}`);
    }

    return response.json();
  }
}