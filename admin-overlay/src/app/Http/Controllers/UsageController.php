<?php

declare(strict_types=1);

namespace App\Http\Controllers;

use App\Models\Eloquent\UsageEvent;
use Illuminate\Http\Request;
use Inertia\Inertia;
use Inertia\Response;

class UsageController extends Controller
{
    public function index(Request $request): Response
    {
        $organization = $request->user()?->primaryOrganization();
        $organization?->load('plan');

        $events = UsageEvent::query()
            ->with('user:id,name,email')
            ->when($organization, fn ($query) => $query->where('organization_id', $organization->id))
            ->latest()
            ->limit(50)
            ->get()
            ->map(fn (UsageEvent $event): array => [
                'id' => $event->id,
                'user' => $event->user?->name,
                'model' => $event->model,
                'tokens' => $event->totalTokens(),
                'created_at' => $event->created_at?->toDateTimeString(),
            ]);

        return Inertia::render('Usage/Index', [
            'organization' => $organization === null ? null : [
                'name' => $organization->name,
                'plan' => $organization->plan->name,
                'monthly_token_limit' => $organization->monthlyTokenLimit(),
                'tokens_used' => $organization->tokensUsedThisMonth(),
                'remaining_tokens' => $organization->remainingTokensThisMonth(),
            ],
            'events' => $events,
        ]);
    }
}
