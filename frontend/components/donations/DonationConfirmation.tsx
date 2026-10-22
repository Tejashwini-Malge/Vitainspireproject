"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import type { Campaign, PaymentInitiate, SocialShareOut } from "@/lib/types";
import { SocialShareButtons } from "@/components/donations/SocialShareButtons";

interface DonationConfirmationProps {
  campaign: Campaign;
  paymentData: PaymentInitiate;
  amount: number;
  donorName: string;
  isRecurring: boolean;
  frequency?: string | null;
}

interface RazorpayWindow extends Window {
  Razorpay?: {
    new (options: any): {
      open(): void;
    };
  };
}

export function DonationConfirmation({
  campaign,
  paymentData,
  amount,
  donorName,
  isRecurring,
  frequency,
}: DonationConfirmationProps) {
  const [paymentComplete, setPaymentComplete] = useState(false);
  const [paymentError, setPaymentError] = useState<string>("");
  const [showSocialShare, setShowSocialShare] = useState(false);

  // Load Razorpay script
  useEffect(() => {
    const script = document.createElement("script");
    script.src = "https://checkout.razorpay.com/v1/checkout.js";
    script.async = true;
    document.head.appendChild(script);

    return () => {
      document.head.removeChild(script);
    };
  }, []);

  const handlePayment = () => {
    const razorpayWindow = window as RazorpayWindow;

    if (!razorpayWindow.Razorpay) {
      setPaymentError("Payment gateway is not available. Please try again.");
      return;
    }

    const options = {
      key: paymentData.key_id,
      amount: paymentData.amount_minor,
      currency: paymentData.currency,
      name: campaign.title,
      description: `Donation to ${campaign.title}`,
      order_id: paymentData.order_id,
      prefill: {
        name: paymentData.customer_name,
        email: paymentData.customer_email,
      },
      handler: async (response: any) => {
        try {
          // Verify payment on backend
          await api(`/payments/verify`, {
            method: "POST",
            body: JSON.stringify({
              payment_id: paymentData.payment_id,
              order_id: paymentData.order_id,
              signature: response.razorpay_signature,
            }),
          });

          setPaymentComplete(true);
          setShowSocialShare(true);
        } catch (err) {
          setPaymentError(
            err instanceof Error ? err.message : "Payment verification failed"
          );
        }
      },
      modal: {
        ondismiss: () => {
          setPaymentError("Payment was cancelled. Please try again.");
        },
      },
    };

    const rzp = new razorpayWindow.Razorpay(options);
    rzp.open();
  };

  if (paymentComplete) {
    return (
      <div className="space-y-8">
        <div className="rounded-lg border-2 border-teal bg-teal/5 p-8 text-center">
          <div className="mb-4 text-5xl">🎉</div>
          <h1 className="mb-2 text-2xl font-semibold text-navy">Thank You!</h1>
          <p className="text-muted">Your donation of ₹{(amount / 100000).toFixed(1)}L has been received</p>
          <p className="mt-2 text-sm text-muted">
            A confirmation email will be sent to you shortly with your tax receipt.
          </p>
        </div>

        {/* Donation Summary */}
        <div className="rounded-lg border-2 border-line bg-white p-6">
          <h2 className="mb-4 font-semibold text-navy">Donation Details</h2>
          <div className="space-y-3">
            <div className="flex items-center justify-between border-b border-line pb-3">
              <span className="text-muted">Campaign</span>
              <span className="font-medium text-navy">{campaign.title}</span>
            </div>
            <div className="flex items-center justify-between border-b border-line pb-3">
              <span className="text-muted">Donor Name</span>
              <span className="font-medium text-navy">{donorName}</span>
            </div>
            <div className="flex items-center justify-between border-b border-line pb-3">
              <span className="text-muted">Amount</span>
              <span className="font-semibold text-teal">₹{(amount / 100).toLocaleString()}</span>
            </div>
            {isRecurring && (
              <div className="flex items-center justify-between border-b border-line pb-3">
                <span className="text-muted">Frequency</span>
                <span className="font-medium text-navy">
                  {frequency === "MONTHLY" ? "Monthly" : frequency === "QUARTERLY" ? "Quarterly" : "Yearly"}
                </span>
              </div>
            )}
            <div className="flex items-center justify-between">
              <span className="text-muted">Transaction ID</span>
              <span className="font-mono text-sm text-navy">{paymentData.payment_id.slice(0, 12)}...</span>
            </div>
          </div>
        </div>

        {/* Social Share Section */}
        {showSocialShare && (
          <div className="rounded-lg border-2 border-line bg-white p-6">
            <h2 className="mb-4 font-semibold text-navy">Share Your Donation</h2>
            <p className="mb-4 text-sm text-muted">
              Help us reach more people. Share this campaign with your network.
            </p>
            <SocialShareButtons campaignId={campaign.id} donorName={donorName} amount={amount} />
          </div>
        )}

        {/* Next Steps */}
        <div className="rounded-lg border-2 border-line bg-paper p-6">
          <h3 className="mb-3 font-semibold text-navy">What's Next?</h3>
          <ul className="space-y-2 text-sm text-muted">
            <li>✓ Check your email for a confirmation receipt</li>
            <li>✓ Your tax receipt (80G eligible) will be sent separately</li>
            {isRecurring && (
              <>
                <li>✓ Your {frequency?.toLowerCase()} donations are now active</li>
                <li>✓ You can manage your subscription anytime from your dashboard</li>
              </>
            )}
            <li>✓ Track the campaign's progress on this page</li>
          </ul>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6 rounded-lg border-2 border-line bg-white p-8">
      <div className="text-center">
        <h2 className="mb-2 text-2xl font-semibold text-navy">Complete Your Donation</h2>
        <p className="text-muted">
          Amount: <span className="font-bold text-teal">₹{(amount / 100).toLocaleString()}</span>
        </p>
        {isRecurring && (
          <p className="text-sm text-muted">
            {frequency === "MONTHLY" ? "Monthly" : frequency === "QUARTERLY" ? "Quarterly" : "Yearly"} recurring donation
          </p>
        )}
      </div>

      {paymentError && (
        <div role="alert" className="rounded-sm border-2 border-status-rejected bg-status-rejected/5 p-4">
          <p className="text-sm text-status-rejected">{paymentError}</p>
        </div>
      )}

      <button
        onClick={handlePayment}
        className="w-full rounded-sm bg-teal px-6 py-4 font-display font-medium text-paper hover:bg-teal/90"
      >
        Pay with Razorpay
      </button>

      <p className="text-center text-xs text-muted">
        Your payment is secure and encrypted. We use Razorpay for secure payment processing.
      </p>
    </div>
  );
}
