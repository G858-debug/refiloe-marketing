import React from 'react';
import { Smartphone, Sparkles, TrendingUp, ArrowRight } from 'lucide-react';

interface Step {
  number: number;
  title: string;
  description: string;
  Icon: React.ComponentType<{ className?: string }>;
}

const steps: Step[] = [
  {
    number: 1,
    title: 'CONNECT',
    description: 'Link your WhatsApp in 5 minutes',
    Icon: Smartphone,
  },
  {
    number: 2,
    title: 'AUTOMATE',
    description: 'Refiloe handles the admin',
    Icon: Sparkles,
  },
  {
    number: 3,
    title: 'GROW',
    description: 'Triple your client load',
    Icon: TrendingUp,
  },
];

export default function HowItWorks() {
  return (
    <div className="w-full max-w-4xl mx-auto px-4 py-8">
      {/* Section title */}
      <h2 className="text-2xl md:text-3xl font-bold text-[#674636] text-center mb-12">
        How It Works
      </h2>

      {/* Steps container */}
      <div className="flex flex-col md:flex-row items-center justify-center gap-4 md:gap-0">
        {steps.map((step, index) => (
          <React.Fragment key={step.number}>
            {/* Step card */}
            <div className="flex flex-col items-center text-center w-full md:w-56">
              {/* Circle with icon */}
              <div className="relative">
                {/* Main circle */}
                <div className="w-28 h-28 md:w-32 md:h-32 rounded-full bg-[#AAB396] flex items-center justify-center shadow-lg transition-transform hover:scale-105">
                  <step.Icon className="w-12 h-12 md:w-14 md:h-14 text-white" strokeWidth={1.5} />
                </div>

                {/* Step number badge */}
                <div className="absolute -top-2 -right-2 w-10 h-10 rounded-full bg-[#674636] text-white flex items-center justify-center font-bold text-lg shadow-md">
                  {step.number}
                </div>
              </div>

              {/* Title */}
              <h3 className="mt-4 text-xl font-bold text-[#674636]">
                {step.title}
              </h3>

              {/* Description */}
              <p className="mt-2 text-gray-600 text-sm md:text-base">
                {step.description}
              </p>
            </div>

            {/* Connector arrow (not after last step) */}
            {index < steps.length - 1 && (
              <>
                {/* Desktop arrow */}
                <div className="hidden md:flex items-center justify-center w-16 -mt-12">
                  <ArrowRight className="w-8 h-8 text-[#AAB396]" />
                </div>

                {/* Mobile arrow */}
                <div className="md:hidden flex items-center justify-center py-2">
                  <ArrowRight className="w-6 h-6 text-[#AAB396] rotate-90" />
                </div>
              </>
            )}
          </React.Fragment>
        ))}
      </div>

      {/* Bottom CTA hint */}
      <div className="mt-12 text-center">
        <p className="text-[#674636] font-medium">
          Ready to get started?
        </p>
        <div className="mt-2 inline-flex items-center gap-2 text-[#AAB396]">
          <Sparkles className="w-4 h-4" />
          <span className="text-sm">Takes just 5 minutes to set up</span>
          <Sparkles className="w-4 h-4" />
        </div>
      </div>
    </div>
  );
}
