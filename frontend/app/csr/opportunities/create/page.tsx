'use client';

import { useState } from 'react';
import { useRouter } from 'next/navigation';
import { api } from '@/lib/api';
import { PageHeader } from '@/components/ui/page-header';
import { Card } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Textarea } from '@/components/ui/textarea';

export default function CreateOpportunityPage() {
  const router = useRouter();
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [formData, setFormData] = useState({
    title: '',
    description: '',
    sectors: [] as string[],
    geographies: [] as string[],
    budget_min: '',
    budget_max: '',
    deadline: '',
    requirements_text: '',
  });

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setError('');

    try {
      const data = await api<{ id: string }>('/csr/opportunities', {
        method: 'POST',
        body: JSON.stringify({
          ...formData,
          sectors: formData.sectors.filter(s => s),
          geographies: formData.geographies.filter(g => g),
          budget_min: parseInt(formData.budget_min),
          budget_max: parseInt(formData.budget_max),
        }),
      });
      router.push(`/csr/opportunities/${data.id}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to create opportunity');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="mx-auto max-w-2xl space-y-8">
      <PageHeader eyebrow="CSR workspace" title="Create New Opportunity" />

      {error && (
        <p role="alert" className="rounded-sm border border-status-rejected/40 bg-status-rejected/10 px-4 py-3 text-sm text-status-rejected">
          {error}
        </p>
      )}

      <Card className="p-6">
        <form onSubmit={handleSubmit} className="space-y-6">
          <div>
            <label className="mb-2 block font-medium text-navy">Title</label>
            <Input
              type="text"
              value={formData.title}
              onChange={e => setFormData({ ...formData, title: e.target.value })}
              minLength={5}
              required
            />
          </div>

          <div>
            <label className="mb-2 block font-medium text-navy">Description</label>
            <Textarea
              value={formData.description}
              onChange={e => setFormData({ ...formData, description: e.target.value })}
              rows={4}
              minLength={10}
              required
            />
          </div>

          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="mb-2 block font-medium text-navy">Budget Min (₹)</label>
              <Input
                type="number"
                value={formData.budget_min}
                onChange={e => setFormData({ ...formData, budget_min: e.target.value })}
                required
              />
            </div>
            <div>
              <label className="mb-2 block font-medium text-navy">Budget Max (₹)</label>
              <Input
                type="number"
                value={formData.budget_max}
                onChange={e => setFormData({ ...formData, budget_max: e.target.value })}
                required
              />
            </div>
          </div>

          <div>
            <label className="mb-2 block font-medium text-navy">Deadline</label>
            <Input
              type="date"
              value={formData.deadline}
              onChange={e => setFormData({ ...formData, deadline: e.target.value })}
              required
            />
          </div>

          <div>
            <label className="mb-2 block font-medium text-navy">Sectors (comma-separated)</label>
            <Input
              type="text"
              value={formData.sectors.join(', ')}
              onChange={e => setFormData({ ...formData, sectors: e.target.value.split(',').map(s => s.trim()) })}
              placeholder="health, education, water"
              required
            />
          </div>

          <div>
            <label className="mb-2 block font-medium text-navy">Geographies (comma-separated)</label>
            <Input
              type="text"
              value={formData.geographies.join(', ')}
              onChange={e => setFormData({ ...formData, geographies: e.target.value.split(',').map(g => g.trim()) })}
              placeholder="Karnataka, Tamil Nadu"
              required
            />
          </div>

          <div>
            <label className="mb-2 block font-medium text-navy">Requirements</label>
            <Textarea
              value={formData.requirements_text}
              onChange={e => setFormData({ ...formData, requirements_text: e.target.value })}
              rows={3}
              minLength={10}
              required
            />
          </div>

          <div className="flex gap-4 border-t border-line pt-6">
            <Button type="submit" variant="primary" disabled={loading}>
              {loading ? 'Creating...' : 'Create Opportunity'}
            </Button>
            <Button type="button" variant="secondary" onClick={() => router.back()}>
              Cancel
            </Button>
          </div>
        </form>
      </Card>
    </div>
  );
}
