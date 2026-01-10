import React from 'react';
import {
  Calendar,
  CreditCard,
  Dumbbell,
  TrendingUp,
  MessageCircle,
  LayoutDashboard
} from 'lucide-react';

interface Feature {
  title: string;
  description: string;
  Icon: React.ComponentType<{ className?: string }>;
}

const features: Feature[] = [
  {
    title: 'Smart Booking',
    description: 'Clients book 24/7',
    Icon: Calendar,
  },
  {
    title: 'Auto Payments',
    description: 'No more chasing',
    Icon: CreditCard,
  },
  {
    title: 'AI Workouts',
    description: 'Plans in 2 minutes',
    Icon: Dumbbell,
  },
  {
    title: 'Progress Tracking',
    description: 'Automatic check-ins',
    Icon: TrendingUp,
  },
  {
    title: 'Instant Replies',
    description: '24/7 responses',
    Icon: MessageCircle,
  },
  {
    title: 'Client Dashboard',
    description: 'Everything organized',
    Icon: LayoutDashboard,
  },
];

export default function FeatureIcons() {
  return (
    <div className="w-full max-w-4xl mx-auto px-4 py-8">
      {/* Grid container */}
      <div className="grid grid-cols-2 md:grid-cols-3 gap-4 md:gap-6">
        {features.map((feature) => (
          <div
            key={feature.title}
            className="group bg-white rounded-xl p-6 shadow-sm hover:shadow-lg transition-all duration-300 cursor-pointer border border-transparent hover:border-[#AAB396]/30"
          >
            {/* Icon circle */}
            <div className="w-14 h-14 md:w-16 md:h-16 rounded-full bg-[#AAB396]/20 flex items-center justify-center mb-4 group-hover:bg-[#AAB396]/30 transition-colors">
              <feature.Icon
                className="w-7 h-7 md:w-8 md:h-8 text-[#AAB396] group-hover:text-[#8FA37A] transition-colors"
                strokeWidth={1.5}
              />
            </div>

            {/* Title */}
            <h3 className="text-base md:text-lg font-bold text-[#674636] mb-1">
              {feature.title}
            </h3>

            {/* Description */}
            <p className="text-sm text-gray-600">
              {feature.description}
            </p>
          </div>
        ))}
      </div>

      {/* Optional bottom text */}
      <div className="mt-8 text-center">
        <p className="text-gray-500 text-sm">
          All features included in every plan
        </p>
      </div>
    </div>
  );
}
