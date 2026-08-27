<?php

declare(strict_types=1);

use App\Http\Controllers\Internal\AgentAccessController;
use App\Http\Middleware\VerifyInternalToken;
use Illuminate\Support\Facades\Route;

Route::middleware(VerifyInternalToken::class)->prefix('internal')->group(function (): void {
    Route::get('/agent-access', [AgentAccessController::class, 'show']);
    Route::post('/usage', [AgentAccessController::class, 'store']);
});
