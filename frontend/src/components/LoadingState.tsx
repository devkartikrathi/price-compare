import React from 'react';
import { Search, CreditCard, TrendingUp } from 'lucide-react';

export const LoadingState: React.FC = () => {
  return (
    <div className="text-center py-16">
      <div className="relative inline-block mb-8">
        {/* Animated search icon */}
        <div className="w-20 h-20 bg-gradient-to-r from-indigo-600 to-purple-600 rounded-full flex items-center justify-center mb-4 animate-pulse">
          <Search className="w-10 h-10 text-white" />
        </div>
        
        {/* Floating elements */}
        <div className="absolute -top-2 -right-2 w-8 h-8 bg-emerald-500 rounded-full flex items-center justify-center animate-bounce">
          <CreditCard className="w-4 h-4 text-white" />
        </div>
        <div className="absolute -bottom-2 -left-2 w-8 h-8 bg-yellow-500 rounded-full flex items-center justify-center animate-bounce animation-delay-300">
          <TrendingUp className="w-4 h-4 text-white" />
        </div>
      </div>

      <h3 className="text-2xl font-bold text-gray-900 mb-2">
        Finding the Best Deals
      </h3>
      <p className="text-gray-600 mb-8 max-w-md mx-auto">
        We're analyzing prices across multiple platforms and applying your credit card benefits to find you the best deals.
      </p>

      {/* Progress steps */}
      <div className="max-w-md mx-auto space-y-4">
        {[
          'Searching products across platforms...',
          'Analyzing credit card offers...',
          'Calculating best prices...',
          'Organizing results...'
        ].map((step, index) => (
          <div
            key={index}
            className="flex items-center gap-3 text-left animate-pulse"
            style={{ animationDelay: `${index * 0.5}s` }}
          >
            <div className="w-2 h-2 bg-indigo-600 rounded-full"></div>
            <span className="text-gray-700">{step}</span>
          </div>
        ))}
      </div>
    </div>
  );
};