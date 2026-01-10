import React from 'react';
import {
  Coins,
  Clock,
  Calculator,
  Users,
  Banknote,
  TrendingUp,
  ArrowDown,
  Sparkles
} from 'lucide-react';

interface ReturnItem {
  icon: React.ComponentType<{ className?: string }>;
  label: string;
  value: string;
  highlight?: boolean;
}

const returnItems: ReturnItem[] = [
  { icon: Clock, label: 'Hours saved weekly', value: '15+' },
  { icon: Calculator, label: 'Your hourly value', value: 'R200+' },
  { icon: Banknote, label: 'Monthly time saved', value: 'R12,000+', highlight: true },
  { icon: Users, label: 'Extra clients possible', value: '5-10' },
  { icon: Coins, label: 'Revenue per client', value: 'R1,500+' },
  { icon: TrendingUp, label: 'Monthly revenue boost', value: 'R7,500+', highlight: true },
];

export default function ROICalculator() {
  return (
    <div className="w-full max-w-xl mx-auto px-4 py-8">
      {/* Main container */}
      <div className="relative">

        {/* Investment Box */}
        <div className="bg-[#674636] rounded-2xl p-6 text-white text-center shadow-lg">
          <p className="text-sm uppercase tracking-wide text-[#F7EED3] mb-2">
            Your Investment
          </p>
          <div className="flex items-center justify-center gap-2">
            <Coins className="w-6 h-6 text-[#AAB396]" />
            <span className="text-4xl font-bold">R199</span>
            <span className="text-lg text-[#F7EED3]">/month</span>
          </div>
          <p className="text-sm text-[#F7EED3] mt-2">
            Refiloe subscription
          </p>
        </div>

        {/* Arrow connector */}
        <div className="flex justify-center py-4">
          <div className="flex flex-col items-center">
            <ArrowDown className="w-8 h-8 text-[#AAB396] animate-bounce" />
            <span className="text-xs text-gray-500 mt-1">transforms into</span>
          </div>
        </div>

        {/* Returns Box */}
        <div className="bg-[#FFF8E8] rounded-2xl p-6 shadow-lg border-2 border-[#F7EED3]">
          <p className="text-sm uppercase tracking-wide text-[#674636] mb-4 text-center font-semibold">
            Your Return
          </p>

          <div className="grid grid-cols-2 gap-4">
            {returnItems.map((item, index) => (
              <div
                key={index}
                className={`flex items-center gap-3 p-3 rounded-lg ${
                  item.highlight
                    ? 'bg-[#AAB396]/20 border border-[#AAB396]'
                    : 'bg-white'
                }`}
              >
                <div className="flex-shrink-0 w-10 h-10 rounded-full bg-[#AAB396]/30 flex items-center justify-center">
                  <item.icon className="w-5 h-5 text-[#674636]" />
                </div>
                <div className="min-w-0">
                  <p className="text-xs text-gray-500 truncate">{item.label}</p>
                  <p className={`font-bold text-[#674636] ${item.highlight ? 'text-lg' : 'text-base'}`}>
                    {item.value}
                  </p>
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* Arrow connector */}
        <div className="flex justify-center py-4">
          <div className="flex flex-col items-center">
            <ArrowDown className="w-8 h-8 text-[#674636]" />
            <span className="text-xs text-gray-500 mt-1">equals</span>
          </div>
        </div>

        {/* ROI Result */}
        <div className="bg-[#AAB396] rounded-2xl p-8 text-center shadow-xl relative overflow-hidden">
          {/* Decorative elements */}
          <div className="absolute top-2 left-4">
            <Sparkles className="w-6 h-6 text-white/30" />
          </div>
          <div className="absolute bottom-4 right-6">
            <Sparkles className="w-8 h-8 text-white/30" />
          </div>
          <div className="absolute top-1/2 left-2 -translate-y-1/2">
            <Coins className="w-5 h-5 text-white/20" />
          </div>

          <p className="text-sm uppercase tracking-wide text-white/80 mb-2">
            Total ROI
          </p>
          <div className="text-6xl md:text-7xl font-black text-white mb-2">
            50-100X
          </div>
          <p className="text-white/90 font-medium">
            Return on your investment
          </p>

          {/* Bottom highlight */}
          <div className="mt-4 inline-flex items-center gap-2 bg-white/20 rounded-full px-4 py-2">
            <TrendingUp className="w-4 h-4 text-white" />
            <span className="text-sm text-white font-medium">
              Pays for itself in hours, not days
            </span>
          </div>
        </div>

        {/* Decorative coin icons scattered around */}
        <div className="absolute -top-2 -right-2 opacity-20">
          <Coins className="w-12 h-12 text-[#674636]" />
        </div>
        <div className="absolute -bottom-2 -left-2 opacity-20">
          <TrendingUp className="w-10 h-10 text-[#AAB396]" />
        </div>
      </div>
    </div>
  );
}
