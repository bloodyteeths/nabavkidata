import { redirect } from 'next/navigation';

/**
 * Subscription plans are retired: the service is billed per bid by invoice
 * (фактура), not by card subscription. Any old link to /billing/plans lands
 * on the service page instead.
 */
export default function PlansPage() {
  redirect('/usluga?src=billing_plans');
}
