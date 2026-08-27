<?php

declare(strict_types=1);

namespace App\Http\Controllers;

use Inertia\Inertia;
use Inertia\Response;

class SkillsController extends Controller
{
    public function index(): Response
    {
        return Inertia::render('Skills/Index', [
            'agentUrl' => rtrim((string) config('services.agent.url'), '/'),
        ]);
    }
}
