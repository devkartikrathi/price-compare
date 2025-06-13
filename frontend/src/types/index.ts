export interface Product {
  product_title: string;
  product_url: string;
  platform: string;
  original_price: number;
  total_discount: number;
  effective_price: number;
  savings_percentage: number;
  recommended_card: string | null;
  card_benefit_description: string | null;
  confidence_score: number;
}

export interface PriceAnalysisRequest {
  product_query: string;
  user_credit_cards: string[];
  max_products_per_platform?: number;
}

export interface PriceAnalysisResponse {
  products: Product[];
}

export interface SupportedCard {
  name: string;
  selected: boolean;
}

export interface Platform {
  name: string;
  logo: string;
}