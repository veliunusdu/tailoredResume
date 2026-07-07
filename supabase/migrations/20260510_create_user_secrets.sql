-- Migration: Create user_secrets table
-- Description: Stores encrypted user credentials (API keys, passwords)

-- Create table for encrypted user secrets
CREATE TABLE IF NOT EXISTS public.user_secrets (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    secret_type TEXT NOT NULL, -- e.g., 'gemini_api_key', 'linkedin_password'
    encrypted_value TEXT NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT timezone('utc'::text, now()) NOT NULL,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT timezone('utc'::text, now()) NOT NULL,
    UNIQUE(user_id, secret_type)
);

-- Enable Row Level Security
ALTER TABLE public.user_secrets ENABLE ROW LEVEL SECURITY;

-- Create policy so users can only manage their own secrets
-- Note: In Phase 1 we initially said only service role, but user requested this policy.
-- Keeping it restricted to owner for management.
CREATE POLICY "Users can manage their own secrets" ON public.user_secrets
    FOR ALL USING (auth.uid() = user_id);

-- Trigger for updated_at
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ language 'plpgsql';

CREATE TRIGGER update_user_secrets_updated_at
    BEFORE UPDATE ON public.user_secrets
    FOR EACH ROW
    EXECUTE PROCEDURE update_updated_at_column();

