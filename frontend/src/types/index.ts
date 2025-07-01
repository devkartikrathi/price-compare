export interface CreditCardBenefits {
  reward_points_earned: number;
  reward_points_value: number;
  cashback_earned: number;
  effective_cashback_rate: number;
  annual_fee: string;
  welcome_offer: string;
  lounge_access: string;
  other_benefits: string;
  total_value_benefit: number;
}

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
  credit_card_benefits: CreditCardBenefits;
  points_calculation_breakdown: string;
  confidence_score: number;
}

export interface PriceAnalysisRequest {
  product_query: string;
  user_credit_cards: string[];
  max_products_per_platform?: number;
}

export interface PriceAnalysisResponse {
  products: Product[];
  total_products: number;
  query: string;
  timestamp: string;
}

export interface SupportedCard {
  name: string;
  selected: boolean;
}

export interface Platform {
  name: string;
  logo: string;
}