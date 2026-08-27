<?php

declare(strict_types=1);

namespace App\Http\Controllers\Internal;

use App\Http\Controllers\Controller;
use App\Http\Requests\RecordUsageRequest;
use App\Models\Eloquent\Organization;
use App\Models\Eloquent\UsageEvent;
use App\Models\Eloquent\User;
use Illuminate\Http\JsonResponse;
use Illuminate\Http\Request;

class AgentAccessController extends Controller
{
    public function show(Request $request): JsonResponse
    {
        $user = User::query()->find($request->integer('user_id'));
        if ($user === null) {
            return response()->json(['message' => 'user not found'], 404);
        }

        $organization = $user->primaryOrganization();
        if ($organization === null) {
            return response()->json(['message' => 'organization not found'], 404);
        }

        $organization->load('plan');

        return response()->json($this->payload($user, $organization));
    }

    public function store(RecordUsageRequest $request): JsonResponse
    {
        $organization = Organization::query()->with('plan')->findOrFail($request->integer('organization_id'));
        $user = User::query()->findOrFail($request->integer('user_id'));

        if (! $organization->users()->where('users.id', $user->id)->exists()) {
            return response()->json(['message' => 'user is not in the organization'], 422);
        }

        if (! $organization->hasRemainingQuota()) {
            return response()->json([
                'message' => 'monthly token quota exceeded',
                'remaining_tokens' => 0,
            ], 402);
        }

        UsageEvent::query()->create($request->validated());
        $organization->refresh();

        return response()->json($this->payload($user, $organization), 201);
    }

    /**
     * @return array<string, mixed>
     */
    private function payload(User $user, Organization $organization): array
    {
        return [
            'user_id' => $user->id,
            'user_name' => $user->name,
            'email' => $user->email,
            'organization_id' => $organization->id,
            'organization_name' => $organization->name,
            'plan' => $organization->plan->name,
            'monthly_token_limit' => $organization->monthlyTokenLimit(),
            'tokens_used' => $organization->tokensUsedThisMonth(),
            'remaining_tokens' => $organization->remainingTokensThisMonth(),
            'allowed' => $organization->hasRemainingQuota(),
        ];
    }
}
