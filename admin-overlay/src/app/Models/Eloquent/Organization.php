<?php

declare(strict_types=1);

namespace App\Models\Eloquent;

use Illuminate\Database\Eloquent\Attributes\Fillable;
use Illuminate\Database\Eloquent\Model;
use Illuminate\Database\Eloquent\Relations\BelongsTo;
use Illuminate\Database\Eloquent\Relations\BelongsToMany;
use Illuminate\Database\Eloquent\Relations\HasMany;
use Illuminate\Support\Carbon;

#[Fillable([
    'name',
    'plan_id',
])]
class Organization extends Model
{
    /**
     * @return BelongsTo<Plan, $this>
     */
    public function plan(): BelongsTo
    {
        return $this->belongsTo(Plan::class);
    }

    /**
     * @return BelongsToMany<User, $this>
     */
    public function users(): BelongsToMany
    {
        return $this->belongsToMany(User::class)->withPivot('role')->withTimestamps();
    }

    /**
     * @return HasMany<UsageEvent, $this>
     */
    public function usageEvents(): HasMany
    {
        return $this->hasMany(UsageEvent::class);
    }

    public function tokensUsedThisMonth(): int
    {
        $start = Carbon::now()->startOfMonth();

        return (int) $this->usageEvents()
            ->where('created_at', '>=', $start)
            ->selectRaw('coalesce(sum(input_tokens + output_tokens), 0) as total')
            ->value('total');
    }

    public function monthlyTokenLimit(): int
    {
        return (int) $this->plan->monthly_token_limit;
    }

    public function remainingTokensThisMonth(): int
    {
        return max(0, $this->monthlyTokenLimit() - $this->tokensUsedThisMonth());
    }

    public function hasRemainingQuota(): bool
    {
        return $this->remainingTokensThisMonth() > 0;
    }
}
