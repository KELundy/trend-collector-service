/**
 * Database Configuration
 *
 * Placeholder configuration for Supabase connection.
 * This file will be used to initialize the Supabase client
 * when we're ready to connect to the actual database.
 */

import dotenv from "dotenv";

dotenv.config();

export const databaseConfig = {
  supabaseUrl: process.env.SUPABASE_URL,
  supabaseAnonKey: process.env.SUPABASE_ANON_KEY,
  supabaseServiceKey: process.env.SUPABASE_SERVICE_ROLE_KEY,
};

/**
 * Placeholder for Supabase client initialization
 *
 * When ready to connect:
 * import { createClient } from '@supabase/supabase-js'
 * export const supabase = createClient(databaseConfig.supabaseUrl, databaseConfig.supabaseAnonKey)
 */

// For now, we export a mock client
export const supabase = {
  from: (table) => ({
    select: () => Promise.resolve({ data: [], error: null }),
    insert: () => Promise.resolve({ data: null, error: null }),
    update: () => Promise.resolve({ data: null, error: null }),
    delete: () => Promise.resolve({ data: null, error: null }),
  }),
  auth: {
    signUp: () => Promise.resolve({ user: null, error: null }),
    signInWithPassword: () => Promise.resolve({ user: null, error: null }),
  },
};
