<?php

declare(strict_types=1);

namespace App\Http\Middleware;

use Closure;
use Illuminate\Http\Request;
use Symfony\Component\HttpFoundation\Response;

class VerifyInternalToken
{
    public function handle(Request $request, Closure $next): Response
    {
        $expected = (string) config('services.internal.token');
        $given = (string) $request->header('X-Internal-Token', '');

        if ($expected === '' || ! hash_equals($expected, $given)) {
            return response()->json(['message' => 'unauthorized'], 401);
        }

        return $next($request);
    }
}
