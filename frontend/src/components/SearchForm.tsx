import React, { useState, useEffect } from 'react';
import { Search, CreditCard, ChevronDown, ChevronUp, X } from 'lucide-react';
import { ApiService } from '../services/api';
import { SupportedCard } from '../types';

interface SearchFormProps {
  onSearch: (query: string, cards: string[]) => void;
  isLoading: boolean;
}

// Fallback list of common credit cards
const FALLBACK_CARDS = [
  'Chase Sapphire Preferred',
  'Chase Sapphire Reserve',
  'Chase Freedom Unlimited',
  'Chase Freedom Flex',
  'American Express Gold Card',
  'American Express Platinum Card',
  'American Express Blue Cash Preferred',
  'Capital One Venture X',
  'Capital One Venture',
  'Capital One Savor',
  'Citi Double Cash',
  'Citi Premier Card',
  'Discover it Cash Back',
  'Bank of America Travel Rewards',
  'Wells Fargo Active Cash'
];

export const SearchForm: React.FC<SearchFormProps> = ({ onSearch, isLoading }) => {
  const [query, setQuery] = useState('');
  const [selectedCards, setSelectedCards] = useState<string[]>([]);
  const [supportedCards, setSupportedCards] = useState<string[]>([]);
  const [showCardSelector, setShowCardSelector] = useState(false);
  const [cardSearchTerm, setCardSearchTerm] = useState('');
  const [apiError, setApiError] = useState<string | null>(null);

  useEffect(() => {
    loadSupportedCards();
  }, []);

  const loadSupportedCards = async () => {
    try {
      const response = await ApiService.getSupportedCards();
      setSupportedCards(response.supported_cards);
      setApiError(null);
    } catch (error) {
      console.error('Failed to load supported cards:', error);
      // Use fallback cards when API is unavailable
      setSupportedCards(FALLBACK_CARDS);
      setApiError('Using offline card list - API unavailable');
    }
  };

  const handleCardToggle = (card: string) => {
    setSelectedCards(prev => 
      prev.includes(card) 
        ? prev.filter(c => c !== card)
        : [...prev, card]
    );
  };

  const removeCard = (card: string) => {
    setSelectedCards(prev => prev.filter(c => c !== card));
  };

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (query.trim() && selectedCards.length > 0) {
      onSearch(query.trim(), selectedCards);
    }
  };

  const filteredCards = supportedCards.filter(card =>
    card.toLowerCase().includes(cardSearchTerm.toLowerCase())
  );

  return (
    <div className="bg-white rounded-2xl shadow-xl p-8 border border-gray-100">
      {apiError && (
        <div className="mb-4 p-3 bg-yellow-50 border border-yellow-200 rounded-lg">
          <p className="text-sm text-yellow-800">{apiError}</p>
        </div>
      )}
      
      <form onSubmit={handleSubmit} className="space-y-6">
        {/* Product Search */}
        <div className="space-y-2">
          <label htmlFor="product-search" className="block text-sm font-semibold text-gray-700">
            What are you looking for?
          </label>
          <div className="relative">
            <Search className="absolute left-4 top-1/2 transform -translate-y-1/2 text-gray-400 w-5 h-5" />
            <input
              id="product-search"
              type="text"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="Search for products (e.g., iPhone 15, Samsung TV, Nike shoes)"
              className="w-full pl-12 pr-4 py-4 border border-gray-200 rounded-xl focus:ring-2 focus:ring-indigo-500 focus:border-transparent transition-all duration-200 text-lg"
              required
            />
          </div>
        </div>

        {/* Credit Cards Selection */}
        <div className="space-y-3">
          <label className="block text-sm font-semibold text-gray-700">
            Select Your Credit Cards
          </label>
          
          {/* Selected Cards Display */}
          {selectedCards.length > 0 && (
            <div className="flex flex-wrap gap-2 mb-3">
              {selectedCards.map((card) => (
                <span
                  key={card}
                  className="inline-flex items-center gap-1 px-3 py-1.5 bg-indigo-100 text-indigo-800 rounded-lg text-sm font-medium"
                >
                  <CreditCard className="w-3 h-3" />
                  {card}
                  <button
                    type="button"
                    onClick={() => removeCard(card)}
                    className="ml-1 hover:bg-indigo-200 rounded-full p-0.5 transition-colors"
                  >
                    <X className="w-3 h-3" />
                  </button>
                </span>
              ))}
            </div>
          )}

          {/* Card Selector Button */}
          <button
            type="button"
            onClick={() => setShowCardSelector(!showCardSelector)}
            className="w-full flex items-center justify-between px-4 py-3 border border-gray-200 rounded-xl hover:border-indigo-300 transition-colors duration-200"
          >
            <span className="flex items-center gap-2 text-gray-700">
              <CreditCard className="w-5 h-5" />
              {selectedCards.length === 0 ? 'Choose your credit cards' : `${selectedCards.length} card(s) selected`}
            </span>
            {showCardSelector ? <ChevronUp className="w-5 h-5" /> : <ChevronDown className="w-5 h-5" />}
          </button>

          {/* Card Selector Dropdown */}
          {showCardSelector && (
            <div className="border border-gray-200 rounded-xl p-4 bg-gray-50 space-y-3">
              {/* Search within cards */}
              <input
                type="text"
                placeholder="Search cards..."
                value={cardSearchTerm}
                onChange={(e) => setCardSearchTerm(e.target.value)}
                className="w-full px-3 py-2 border border-gray-200 rounded-lg focus:ring-2 focus:ring-indigo-500 focus:border-transparent"
              />
              
              {/* Cards List */}
              <div className="max-h-48 overflow-y-auto space-y-2">
                {filteredCards.map((card) => (
                  <label
                    key={card}
                    className="flex items-center gap-3 p-2 rounded-lg hover:bg-white transition-colors cursor-pointer"
                  >
                    <input
                      type="checkbox"
                      checked={selectedCards.includes(card)}
                      onChange={() => handleCardToggle(card)}
                      className="w-4 h-4 text-indigo-600 border-gray-300 rounded focus:ring-indigo-500"
                    />
                    <span className="text-sm text-gray-700">{card}</span>
                  </label>
                ))}
              </div>
            </div>
          )}
        </div>

        {/* Submit Button */}
        <button
          type="submit"
          disabled={isLoading || !query.trim() || selectedCards.length === 0}
          className="w-full bg-gradient-to-r from-indigo-600 to-purple-600 text-white py-4 px-6 rounded-xl font-semibold text-lg shadow-lg hover:shadow-xl transform hover:-translate-y-0.5 transition-all duration-200 disabled:opacity-50 disabled:cursor-not-allowed disabled:transform-none disabled:shadow-lg"
        >
          {isLoading ? (
            <div className="flex items-center justify-center gap-2">
              <div className="w-5 h-5 border-2 border-white border-t-transparent rounded-full animate-spin"></div>
              Finding Best Deals...
            </div>
          ) : (
            'Find Best Prices'
          )}
        </button>
      </form>
    </div>
  );
};