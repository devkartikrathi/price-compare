import React from 'react';
import { ExternalLink, CreditCard, TrendingDown, Star } from 'lucide-react';
import { Product } from '../types';

interface ProductCardProps {
  product: Product;
  isBestDeal?: boolean;
}

export const ProductCard: React.FC<ProductCardProps> = ({ product, isBestDeal }) => {
  const formatPrice = (price: number) => {
    return new Intl.NumberFormat('en-IN', {
      style: 'currency',
      currency: 'INR',
      maximumFractionDigits: 0,
    }).format(price);
  };

  const formatSavings = (savings: number) => {
    return savings.toFixed(1);
  };

  const getPlatformColor = (platform: string) => {
    const colors: { [key: string]: string } = {
      'Amazon': 'bg-yellow-500',
      'Flipkart': 'bg-blue-500',
      'Myntra': 'bg-pink-500',
      'BigBasket': 'bg-green-500',
      'Bigbasket': 'bg-green-500',
      'Blinkit': 'bg-yellow-600',
      'Zepto': 'bg-purple-500',
      'Swiggy': 'bg-orange-500',
      'Nykaa': 'bg-pink-600',
      'FirstCry': 'bg-blue-400',
    };
    return colors[platform] || 'bg-gray-500';
  };

  return (
    <div className={`bg-white rounded-xl shadow-lg hover:shadow-xl transition-all duration-300 border-2 ${
      isBestDeal ? 'border-emerald-400 ring-2 ring-emerald-100' : 'border-gray-100 hover:border-indigo-200'
    } group relative overflow-hidden`}>
      {/* Best Deal Badge */}
      {isBestDeal && (
        <div className="absolute top-0 right-0 bg-gradient-to-r from-emerald-500 to-green-500 text-white px-4 py-1 rounded-bl-xl font-semibold text-sm flex items-center gap-1">
          <Star className="w-4 h-4 fill-current" />
          Best Deal
        </div>
      )}

      {/* Platform Badge */}
      <div className="absolute top-4 left-4 z-10">
        <span className={`${getPlatformColor(product.platform)} text-white px-3 py-1 rounded-full text-sm font-semibold shadow-lg`}>
          {product.platform}
        </span>
      </div>

      <div className="p-6 pt-16">
        {/* Product Title */}
        <h3 className="font-bold text-lg text-gray-900 mb-4 line-clamp-2 leading-tight">
          {product.product_title}
        </h3>

        {/* Price Information */}
        <div className="space-y-3 mb-6">
          <div className="flex items-baseline justify-between">
            <div>
              <p className="text-2xl font-bold text-gray-900">{formatPrice(product.effective_price)}</p>
              {product.total_discount > 0 && (
                <p className="text-sm text-gray-500 line-through">{formatPrice(product.original_price)}</p>
              )}
            </div>
            {product.savings_percentage > 0 && (
              <div className="flex items-center gap-1 bg-green-100 text-green-800 px-2 py-1 rounded-lg">
                <TrendingDown className="w-4 h-4" />
                <span className="font-semibold text-sm">{formatSavings(product.savings_percentage)}% OFF</span>
              </div>
            )}
          </div>

          {product.total_discount > 0 && (
            <p className="text-green-600 font-semibold">
              You save {formatPrice(product.total_discount)}
            </p>
          )}
        </div>

        {/* Credit Card Benefit */}
        {product.recommended_card && product.card_benefit_description && (
          <div className="bg-indigo-50 border border-indigo-200 rounded-lg p-4 mb-4">
            <div className="flex items-start gap-2">
              <CreditCard className="w-5 h-5 text-indigo-600 mt-0.5 flex-shrink-0" />
              <div>
                <p className="font-semibold text-indigo-900 text-sm mb-1">{product.recommended_card}</p>
                <p className="text-indigo-700 text-sm">{product.card_benefit_description}</p>
              </div>
            </div>
          </div>
        )}

        {/* Confidence Score */}
        <div className="flex items-center justify-between mb-4">
          <div className="flex items-center gap-2">
            <div className="flex items-center gap-1">
              <span className="text-sm font-medium text-gray-600">Match Score:</span>
              <div className="flex items-center gap-1">
                {[...Array(5)].map((_, i) => (
                  <Star
                    key={i}
                    className={`w-4 h-4 ${
                      i < Math.round(product.confidence_score * 5)
                        ? 'text-yellow-400 fill-current'
                        : 'text-gray-300'
                    }`}
                  />
                ))}
              </div>
              <span className="text-sm font-semibold text-gray-700">
                {(product.confidence_score * 100).toFixed(0)}%
              </span>
            </div>
          </div>
        </div>

        {/* Action Button */}
        <a
          href={product.product_url}
          target="_blank"
          rel="noopener noreferrer"
          className="w-full bg-gradient-to-r from-indigo-600 to-purple-600 text-white py-3 px-4 rounded-lg font-semibold text-center hover:shadow-lg transform hover:-translate-y-0.5 transition-all duration-200 flex items-center justify-center gap-2 group"
        >
          View on {product.platform}
          <ExternalLink className="w-4 h-4 group-hover:translate-x-0.5 transition-transform" />
        </a>
      </div>
    </div>
  );
};