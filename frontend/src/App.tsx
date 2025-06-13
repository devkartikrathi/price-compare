import React, { useState } from 'react';
import { ShoppingCart, Sparkles, CreditCard } from 'lucide-react';
import { SearchForm } from './components/SearchForm';
import { ResultsSection } from './components/ResultsSection';
import { LoadingState } from './components/LoadingState';
import { ErrorState } from './components/ErrorState';
import { ApiService } from './services/api';
import { Product } from './types';

function App() {
  const [products, setProducts] = useState<Product[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [searchQuery, setSearchQuery] = useState<string>('');
  const [hasSearched, setHasSearched] = useState(false);

  const handleSearch = async (query: string, creditCards: string[]) => {
    setIsLoading(true);
    setError(null);
    setSearchQuery(query);
    setHasSearched(true);

    try {
      const response = await ApiService.analyzeProductPrices({
        product_query: query,
        user_credit_cards: creditCards,
        max_products_per_platform: 5,
      });

      setProducts(response.products || []);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'An unexpected error occurred');
    } finally {
      setIsLoading(false);
    }
  };

  const handleRetry = () => {
    setError(null);
    setHasSearched(false);
    setProducts([]);
  };

  return (
    <div className="min-h-screen bg-gradient-to-br from-indigo-50 via-white to-emerald-50">
      {/* Header */}
      <header className="relative overflow-hidden bg-gradient-to-r from-indigo-600 via-purple-600 to-emerald-600 text-white">
        <div className="absolute inset-0 bg-black/10"></div>
        <div className="relative max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-16 sm:py-24">
          <div className="text-center">
            <div className="flex items-center justify-center gap-3 mb-6">
              <div className="p-3 bg-white/20 rounded-xl backdrop-blur-sm">
                <ShoppingCart className="w-8 h-8" />
              </div>
              <h1 className="text-4xl sm:text-5xl lg:text-6xl font-bold">
                Smart<span className="text-yellow-300">Price</span>
              </h1>
            </div>
            
            <p className="text-xl sm:text-2xl font-light mb-8 max-w-3xl mx-auto leading-relaxed">
              Find the best deals across e-commerce platforms with 
              <span className="font-semibold text-yellow-300"> credit card optimization</span>
            </p>

            <div className="flex flex-col sm:flex-row items-center justify-center gap-6 text-sm sm:text-base">
              <div className="flex items-center gap-2">
                <Sparkles className="w-5 h-5 text-yellow-300" />
                <span>Multi-platform comparison</span>
              </div>
              <div className="flex items-center gap-2">
                <CreditCard className="w-5 h-5 text-emerald-300" />
                <span>Credit card benefits</span>
              </div>
              <div className="flex items-center gap-2">
                <ShoppingCart className="w-5 h-5 text-blue-300" />
                <span>Best price guarantee</span>
              </div>
            </div>
          </div>
        </div>
      </header>

      {/* Main Content */}
      <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-12">
        {/* Search Form */}
        <div className="max-w-4xl mx-auto mb-12">
          <SearchForm onSearch={handleSearch} isLoading={isLoading} />
        </div>

        {/* Content Area */}
        <div className="max-w-7xl mx-auto">
          {isLoading && <LoadingState />}
          
          {error && (
            <ErrorState error={error} onRetry={handleRetry} />
          )}

          {!isLoading && !error && hasSearched && (
            <ResultsSection products={products} searchQuery={searchQuery} />
          )}

          {!hasSearched && !isLoading && !error && (
            <div className="text-center py-16">
              <div className="w-32 h-32 bg-gradient-to-r from-indigo-100 to-purple-100 rounded-full flex items-center justify-center mx-auto mb-8">
                <ShoppingCart className="w-16 h-16 text-indigo-600" />
              </div>
              <h3 className="text-2xl font-bold text-gray-900 mb-4">
                Ready to find amazing deals?
              </h3>
              <p className="text-gray-600 max-w-md mx-auto mb-8">
                Search for any product and select your credit cards to discover the best prices with optimized savings.
              </p>
              <div className="grid grid-cols-1 sm:grid-cols-3 gap-6 max-w-2xl mx-auto">
                <div className="text-center p-4">
                  <div className="w-12 h-12 bg-indigo-100 rounded-lg flex items-center justify-center mx-auto mb-3">
                    <span className="text-xl font-bold text-indigo-600">1</span>
                  </div>
                  <h4 className="font-semibold text-gray-900 mb-1">Search Product</h4>
                  <p className="text-sm text-gray-600">Enter what you want to buy</p>
                </div>
                <div className="text-center p-4">
                  <div className="w-12 h-12 bg-purple-100 rounded-lg flex items-center justify-center mx-auto mb-3">
                    <span className="text-xl font-bold text-purple-600">2</span>
                  </div>
                  <h4 className="font-semibold text-gray-900 mb-1">Select Cards</h4>
                  <p className="text-sm text-gray-600">Choose your credit cards</p>
                </div>
                <div className="text-center p-4">
                  <div className="w-12 h-12 bg-emerald-100 rounded-lg flex items-center justify-center mx-auto mb-3">
                    <span className="text-xl font-bold text-emerald-600">3</span>
                  </div>
                  <h4 className="font-semibold text-gray-900 mb-1">Get Best Deal</h4>
                  <p className="text-sm text-gray-600">See optimized prices</p>
                </div>
              </div>
            </div>
          )}
        </div>
      </main>

      {/* Footer */}
      <footer className="bg-gray-900 text-white mt-20">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-12">
          <div className="text-center">
            <div className="flex items-center justify-center gap-2 mb-4">
              <ShoppingCart className="w-6 h-6" />
              <span className="text-xl font-bold">SmartPrice</span>
            </div>
            <p className="text-gray-400 max-w-md mx-auto">
              Your intelligent shopping companion for finding the best deals with credit card optimization.
            </p>
          </div>
          <div className="mt-8 pt-8 border-t border-gray-800 text-center text-gray-400 text-sm">
            <p>&copy; 2025 SmartPrice. Made with ❤️ for smart shoppers.</p>
          </div>
        </div>
      </footer>
    </div>
  );
}

export default App;