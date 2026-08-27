<?php

declare(strict_types=1);

namespace Database\Seeders;

use App\Models\Eloquent\Organization;
use App\Models\Eloquent\Plan;
use App\Models\Eloquent\User;
use Illuminate\Database\Seeder;

class DatabaseSeeder extends Seeder
{
    public function run(): void
    {
        $plan = Plan::query()->firstOrCreate(
            ['name' => 'PoC'],
            ['monthly_token_limit' => 200_000],
        );

        $organization = Organization::query()->firstOrCreate(
            ['name' => 'デモ組織'],
            ['plan_id' => $plan->id],
        );

        $user = User::query()->firstOrCreate(
            ['email' => 'admin@example.com'],
            [
                'name' => '管理者',
                'password' => 'password',
                'email_verified_at' => now(),
            ],
        );

        if (! $organization->users()->where('users.id', $user->id)->exists()) {
            $organization->users()->attach($user->id, ['role' => 'admin']);
        }
    }
}
