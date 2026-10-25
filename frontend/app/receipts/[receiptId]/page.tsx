"use client";

import { useRouter, useParams } from "next/navigation";
import { useEffect, useState } from "react";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { PageHeader } from "@/components/ui/page-header";
import { api, ApiError } from "@/lib/api";
import type { TaxReceipt } from "@/lib/types";

/** The API returns TaxReceiptOut directly; no extra client-only fields are needed. */
type TaxReceiptData = TaxReceipt;

export default function ReceiptPage() {
  const router = useRouter();
  const params = useParams()!;
  const receiptId = params?.receiptId as string;

  const [receipt, setReceipt] = useState<TaxReceiptData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string>("");

  useEffect(() => {
    if (!receiptId) return;

    async function loadReceipt() {
      try {
        setLoading(true);
        const data = await api<TaxReceiptData>(`/receipts/${receiptId}`);
        setReceipt(data);
      } catch (err) {
        if (err instanceof ApiError && err.status === 404) {
          setError("Receipt not found");
        } else {
          setError(err instanceof Error ? err.message : "Could not load receipt");
        }
      } finally {
        setLoading(false);
      }
    }

    loadReceipt();
  }, [receiptId]);

  if (loading) {
    return <p className="text-muted">Loading receipt...</p>;
  }

  if (error || !receipt) {
    return (
      <div className="space-y-4">
        <h1 className="text-2xl font-semibold text-navy">Receipt Not Found</h1>
        <p className="text-muted">{error}</p>
        <Button onClick={() => router.back()}>Go Back</Button>
      </div>
    );
  }

  const receiptDate = new Date(receipt.receipt_date);
  const donationAmount = receipt.amount_minor / 100;

  return (
    <div className="space-y-6">
      {/* Receipt Header */}
      <PageHeader
        eyebrow="80G compliant donation receipt"
        title="Tax Receipt"
        action={<Button onClick={() => window.print()}>Print</Button>}
      />

      {/* Receipt Document */}
      <Card className="space-y-6 p-8 print:border-0">
        {/* Organization Header */}
        <div className="border-b-2 border-line pb-6">
          <p className="text-sm font-semibold text-teal uppercase">Receipt from</p>
          <h2 className="mt-1 text-xl font-semibold text-navy">{receipt.ngo_name}</h2>
          {receipt.ngo_80g_number && (
            <p className="text-sm text-muted">
              80G Certificate: {receipt.ngo_80g_number}
            </p>
          )}
          {receipt.ngo_registration_number && (
            <p className="text-sm text-muted">
              Registration: {receipt.ngo_registration_number}
            </p>
          )}
        </div>

        {/* Receipt Number and Date */}
        <div className="grid grid-cols-2 gap-6">
          <div>
            <p className="text-xs font-medium uppercase text-muted">Receipt Number</p>
            <p className="mt-1 font-mono text-lg font-semibold text-navy">
              {receipt.receipt_number}
            </p>
          </div>
          <div>
            <p className="text-xs font-medium uppercase text-muted">Receipt Date</p>
            <p className="mt-1 text-lg font-semibold text-navy">
              {receiptDate.toLocaleDateString("en-IN", {
                year: "numeric",
                month: "long",
                day: "numeric",
              })}
            </p>
          </div>
        </div>

        {/* Donor Information */}
        <div className="rounded-sm bg-paper p-4">
          <p className="text-xs font-medium uppercase text-muted">Donation Received From</p>
          <p className="mt-2 text-lg font-semibold text-navy">{receipt.donor_name}</p>
          <p className="text-sm text-muted">{receipt.donor_email}</p>
          {receipt.donor_pan && (
            <p className="mt-1 text-sm text-muted">PAN: {receipt.donor_pan}</p>
          )}
        </div>

        {/* Donation Amount */}
        <div className="rounded-sm border border-teal bg-teal/5 p-4">
          <p className="text-xs font-medium uppercase text-muted">Donation Amount</p>
          <p className="mt-2 text-4xl font-semibold text-teal">
            ₹{donationAmount.toLocaleString("en-IN", {
              minimumFractionDigits: 2,
              maximumFractionDigits: 2,
            })}
          </p>
          <p className="mt-1 text-sm text-muted">{receipt.currency}</p>
        </div>

        {/* Tax Information */}
        <div className="rounded-sm border border-dashed border-line p-4">
          <p className="text-xs font-medium uppercase text-muted">Tax Compliance</p>
          <ul className="mt-3 space-y-2 text-sm text-navy">
            <li>This receipt acknowledges donation for charitable purposes</li>
            <li>Donation is eligible under Section 80G of the Income Tax Act</li>
            <li>
              As per the Organization's 80G Certificate, a portion of this
              donation may be deductible
            </li>
            <li>Donor should verify specific deductibility limits with their CA</li>
          </ul>
        </div>

        {/* Footer */}
        <div className="border-t-2 border-line pt-6 text-center text-xs text-muted">
          <p>This is a digitally generated receipt from Vitainspire</p>
          <p>
            Receipt ID: <span className="font-mono">{receipt.id.slice(0, 8)}</span>
          </p>
          {receipt.email_sent_at && (
            <p>
              Email sent:{" "}
              {new Date(receipt.email_sent_at).toLocaleDateString("en-IN")}
            </p>
          )}
        </div>
      </Card>

      {/* Actions */}
      <div className="flex gap-3">
        <Button onClick={() => window.print()} className="flex-1">
          Print Receipt
        </Button>
        <Button
          variant="secondary"
          onClick={() => {
            const element = document.querySelector(".print\\:border-0");
            if (element) {
              const html2pdf = (window as any).html2pdf;
              if (html2pdf) {
                html2pdf().set({ margin: 10, filename: `${receipt.receipt_number}.pdf` }).save();
              }
            }
          }}
          className="flex-1"
        >
          Download PDF
        </Button>
      </div>

      {/* Tax Disclaimer */}
      <Card className="border-status-pending/30 bg-status-pending/5 p-4 text-xs text-status-pending">
        <p className="font-medium">Tax Disclaimer</p>
        <p className="mt-2 text-muted">
          This receipt is provided for your tax documentation. The deductibility of this
          donation under Section 80G depends on the Organization's current 80G
          certificate status. Please verify deductibility limits with your Chartered
          Accountant or tax advisor before claiming deductions.
        </p>
      </Card>
    </div>
  );
}
