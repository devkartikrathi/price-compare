import React from 'react';
import { TrendingUp, Award, ShoppingBag } from 'lucide-react';
import { Product } from '../types';
import { ProductCard } from './ProductCard';

interface ResultsSectionProps {
  products: Product[];
  searchQuery: string;
}

export const ResultsSection: React.FC<ResultsSectionProps> = ({ products, searchQuery }) => {
  if (products.length === 0) {
    return (
      <div className="text-center py-12">
        <ShoppingBag className="w-16 h-16 text-gray-400 mx-auto mb-4" />
        <h3 className="text-xl font-semibold text-gray-600 mb-2">No products found</h3>
        <p className="text-gray-500">Try adjusting your search terms or credit card selection.</p>
      </div>
    );
  }

  // Find the best deal (lowest effective price)
  const bestDeal = products.reduce((best, current) => 
    current.effective_price < best.effective_price ? current : best
  );

  // Group products by platform
  const productsByPlatform = products.reduce((acc, product) => {
    if (!acc[product.platform]) {
      acc[product.platform] = [];
    }
    acc[product.platform].push(product);
    return acc;
  }, {} as { [key: string]: Product[] });

  // Calculate platform statistics
  const platformStats = Object.entries(productsByPlatform).map(([platform, platformProducts]) => {
    const avgPrice = platformProducts.reduce((sum, p) => sum + p.effective_price, 0) / platformProducts.length;
    const bestPrice = Math.min(...platformProducts.map(p => p.effective_price));
    const totalSavings = platformProducts.reduce((sum, p) => sum + p.total_discount, 0);
    
    return {
      platform,
      count: platformProducts.length,
      avgPrice,
      bestPrice,
      totalSavings,
    };
  }).sort((a, b) => a.bestPrice - b.bestPrice);

  const formatPrice = (price: number) => {
    return new Intl.NumberFormat('en-IN', {
      style: 'currency',
      currency: 'INR',
      maximumFractionDigits: 0,
    }).format(price);
  };

  return (
    <div className="space-y-8">
      {/* Results Header */}
      <div className="text-center">
        <h2 className="text-3xl font-bold text-gray-900 mb-2">
          Best Deals for "{searchQuery}"
        </h2>
        <p className="text-gray-600">
          Found {products.length} products across {Object.keys(productsByPlatform).length} platforms
        </p>
      </div>

      {/* Platform Statistics */}
      <div className="bg-white rounded-xl shadow-lg p-6 border border-gray-100">
        <h3 className="text-xl font-semibold text-gray-900 mb-4 flex items-center gap-2">
          <TrendingUp className="w-5 h-5 text-indigo-600" />
          Platform Comparison
        </h3>
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">
          {platformStats.map((stat, index) => (
            <div
              key={stat.platform}
              className={`p-4 rounded-lg border-2 ${
                index === 0 
                  ? 'border-emerald-400 bg-emerald-50' 
                  : 'border-gray-200 bg-gray-50'
              }`}
            >
              <div className="flex items-center justify-between mb-2">
                <h4 className="font-semibold text-gray-900">{stat.platform}</h4>
                {index === 0 && (
                  <Award className="w-4 h-4 text-emerald-600" />
                )}
              </div>
              <div className="space-y-1 text-sm">
                <p className="text-gray-600">
                  <span className="font-medium">Best Price:</span> {formatPrice(stat.bestPrice)}
                </p>
                <p className="text-gray-600">
                  <span className="font-medium">Products:</span> {stat.count}
                </p>
                {stat.totalSavings > 0 && (
                  <p className="text-green-600 font-medium">
                    Total Savings: {formatPrice(stat.totalSavings)}
                  </p>
                )}
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Product Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
        {products
          .sort((a, b) => a.effective_price - b.effective_price)
          .map((product, index) => (
            <ProductCard
              key={`${product.platform}-${product.product_title}-${index}`}
              product={product}
              isBestDeal={product === bestDeal}
            />
          ))}
      </div>
    </div>
  );
};