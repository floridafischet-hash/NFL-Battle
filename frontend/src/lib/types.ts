export type Conference = "AFC" | "NFC";
export type Round = "WILD_CARD" | "DIVISIONAL" | "CONFERENCE" | "SUPER_BOWL";
export type MatchStatus = "OPEN" | "LOCKED" | "FINAL" | "VOID";

export interface Team {
  id: number;
  name: string;
  short_name: string;
  abbreviation: string;
  city: string | null;
  conference: Conference;
  division: string | null;
  logo_url: string | null;
  primary_color: string;
  secondary_color: string;
  is_active: boolean;
  seed: number | null;
}

export interface Me {
  id: string;
  username: string;
  display_name: string;
  avatar_url: string | null;
  role: "USER" | "ADMIN";
  is_admin: boolean;
  is_superuser?: boolean;
}

export interface UserRef {
  id: string;
  display_name: string;
  avatar_url: string | null;
  username?: string;
  is_bot?: boolean;
}

export interface Season {
  id: number;
  name: string;
  year: number;
  status: "DRAFT" | "ACTIVE" | "COMPLETED";
  winner_points: number;
  exact_score_points: number;
  champion_bonus: number;
  score_tips_enabled: boolean;
  lock_minutes_before_kickoff: number;
  champion_team: Team | null;
  completed_at: string | null;
}

export interface Tip {
  winner_team_id: number;
  winner_score: number | null;
  loser_score: number | null;
}

export interface Match {
  id: number;
  season_id: number;
  slot: string;
  round: Round;
  round_label: string;
  conference: Conference | null;
  home_team: Team | null;
  away_team: Team | null;
  kickoff_at: string | null;
  lock_at: string | null;
  venue: string | null;
  status: MatchStatus;
  locked: boolean;
  home_score: number | null;
  away_score: number | null;
  winner_team_id: number | null;
  result_source: string | null;
  finalized_at: string | null;
}

export interface Distribution {
  match_id: number;
  slot: string;
  total: number;
  teams: { team_id: number; count: number; percent: number }[];
}

export interface SeasonMatch extends Match {
  my_pick: Tip | null;
  my_points: number | null;
  distribution: Distribution | null;
}

export type PickState = "none" | "valid" | "pending" | "invalid" | "hidden";

export interface BracketSlot {
  slot: string;
  match_id: number;
  round: Round;
  round_label: string;
  conference: Conference | null;
  home: Team | null;
  away: Team | null;
  teams_source: "actual" | "predicted" | "partial" | "none";
  home_origin: string | null;
  away_origin: string | null;
  status: MatchStatus;
  locked: boolean;
  kickoff_at: string | null;
  lock_at: string | null;
  venue: string | null;
  home_score: number | null;
  away_score: number | null;
  winner_team_id: number | null;
  has_pick: boolean;
  pick_hidden: boolean;
  pick: Tip | null;
  pick_state: PickState;
  effective_winner_team_id: number | null;
  points: number | null;
  winner_correct: boolean | null;
  exact_correct: boolean | null;
  pending_change_request: {
    id: number;
    new_winner_team_id: number;
    new_winner_score: number | null;
    new_loser_score: number | null;
    created_at: string;
  } | null;
}

export interface BracketView {
  season_id: number;
  user: UserRef;
  is_owner: boolean;
  full_visibility: boolean;
  submitted_at: string | null;
  picks_count: number;
  missing_open_picks: number | null;
  champion_team_id: number | null;
  byes: Partial<Record<Conference, Team>>;
  slots: BracketSlot[];
  points: number;
  rank: number | null;
  score_tips_enabled: boolean;
}

export interface LeaderboardRow {
  rank: number;
  previous_rank: number | null;
  user: UserRef;
  points: number;
  correct_winners: number;
  wrong_picks: number;
  missed_picks: number;
  exact_scores: number;
  champion_correct: boolean;
  scored_matches: number;
  is_me: boolean;
}

export interface DashboardData {
  season: Season | null;
  me?: {
    display_name: string;
    rank: number | null;
    participants: number;
    points: number;
    correct_winners: number;
    scored_matches: number;
    total_final_matches: number;
    exact_scores: number;
    champion_correct: boolean;
    missing_open_picks: number;
    submitted_at: string | null;
  };
  next_match?: (Match & { my_pick: Tip | null }) | null;
  recent_results?: Match[];
  leaderboard?: LeaderboardRow[];
  pending_change_requests?: number;
}

export interface ChatMessage {
  id: number;
  created_at: string;
  user: UserRef & { is_bot: boolean };
  body: string;
  image_url: string | null;
  deleted: boolean;
  system: { type: string; payload: Record<string, any> } | null;
}

export interface NotificationItem {
  id: number;
  type: string;
  title: string;
  body: string | null;
  link: string | null;
  read: boolean;
  created_at: string;
}

export interface ChangeRequest {
  id: number;
  status: "PENDING" | "APPROVED" | "REJECTED" | "CANCELLED";
  match_id: number;
  slot: string;
  user: UserRef;
  old: (Tip & { winner_team: Team | null }) | null;
  new: Tip & { winner_team: Team | null };
  reason: string | null;
  created_at: string;
  decided_at: string | null;
  decided_by: string | null;
  decision_note: string | null;
  match: Match;
}

export interface BracketOverviewEntry {
  user: UserRef;
  is_me: boolean;
  picks_count: number;
  missing_open_picks: number;
  submitted_at: string | null;
  champion: Team | null;
  points: number;
  rank: number | null;
}

export interface MatchDetail {
  match: Match;
  season: Season;
  revealed: boolean;
  my_pick: Tip | null;
  my_change_request: ChangeRequest | null;
  distribution: Distribution | null;
  picks: {
    user: UserRef;
    has_pick: boolean;
    pick: Tip | null;
    hidden: boolean;
    points: number | null;
    exact_correct: boolean | null;
    winner_correct: boolean | null;
  }[];
}

export interface SeasonStatsSummary {
  points: number;
  correct_winners: number;
  wrong_picks: number;
  missed_picks: number;
  exact_scores: number;
  scored_matches: number;
  hit_rate: number;
  best_streak: number;
  current_streak: number;
  champion_correct: boolean;
}

export interface UserStats {
  user: UserRef;
  season: (SeasonStatsSummary & { rank: number | null; participants: number }) | null;
  rounds: { round: Round; label: string; correct: number; total: number }[];
  history: {
    season_id: number;
    season_name: string;
    status: string;
    rank: number;
    participants: number;
    points: number;
    correct_winners: number;
    exact_scores: number;
    champion_correct: boolean;
  }[];
  totals: SeasonStatsSummary & { seasons_played: number; titles: number; champion_hits: number };
}

export interface HallOfFameData {
  seasons: {
    season_id: number;
    season_name: string;
    year: number;
    winner_user_id: string | null;
    winner_display_name: string;
    winner_points: number;
    winner_correct_winners: number;
    winner_exact_scores: number;
    champion_team: Team | null;
    winner_sb_pick_team: Team | null;
    standings: {
      rank: number;
      user_id: string;
      display_name: string;
      points: number;
      correct_winners: number;
      exact_scores: number;
      champion_correct: boolean;
      sb_pick_team: Team | null;
    }[];
  }[];
  all_time: {
    rank: number;
    user: UserRef;
    seasons_played: number;
    titles: number;
    total_points: number;
    avg_points: number;
    correct_winners: number;
    exact_scores: number;
    champion_hits: number;
    best_rank: number | null;
  }[];
}
