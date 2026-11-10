import { afterEach, describe, expect, it, vi } from 'vitest';
import { api, ApiError } from './api';

describe('approval API errors', () => {
  afterEach(() => vi.unstubAllGlobals());

  it('sends acknowledgement and includes server criteria in a 409 message', async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(
        JSON.stringify({
          detail: {
            message: 'Client acknowledgement is required.',
            advisory_verdict: 'partial',
            acknowledge_unverified_required: true,
            unverified_criteria: [
              { criterion: 'The cart page is shown.', status: 'missing' },
            ],
          },
        }),
        { status: 409, headers: { 'Content-Type': 'application/json' } },
      ),
    );
    vi.stubGlobal('fetch', fetchMock);

    const error = await api
      .approveMilestone('client-1', 'agreement-1', 'milestone-1', true)
      .catch((reason: unknown) => reason);
    expect(error).toBeInstanceOf(ApiError);
    expect((error as ApiError).status).toBe(409);
    expect((error as Error).message).toBe(
      'Client acknowledgement is required. Unverified criteria: The cart page is shown.',
    );

    const [, options] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(JSON.parse(options.body as string)).toEqual({ acknowledge_unverified: true });
  });
});
