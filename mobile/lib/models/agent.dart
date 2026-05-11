/// The 12 trading agents + Concierge — IDs, display names, families, colors.
/// Mirror of backend's app/schemas/agents.py.
library;

import 'package:ami_trade/theme/ami_theme.dart';
import 'package:flutter/material.dart';

enum AgentFamily {
  analyst,
  researcher,
  manager,
  risk,
  execution,
  concierge,
}

class Agent {
  const Agent({
    required this.id,
    required this.displayName,
    required this.abbreviation,
    required this.family,
    required this.color,
    required this.tagline,
  });

  /// Snake-case ID matching backend (e.g. "fundamentals_analyst").
  final String id;

  /// Human-readable name (e.g., "Fundamentals Analyst").
  final String displayName;

  /// Short label for the hex avatar (e.g., "FUND", "BEAR", "PM").
  final String abbreviation;

  final AgentFamily family;
  final Color color;

  /// One-line role description.
  final String tagline;
}


/// The 12 trading agents + Concierge.
const List<Agent> kAllAgents = [
  // ── Analysts (cyan) ─────────────────────────────────────────
  Agent(
    id: 'fundamentals_analyst',
    displayName: 'Fundamentals Analyst',
    abbreviation: 'FUND',
    family: AgentFamily.analyst,
    color: AmiColors.hexCyan,
    tagline: 'Financials, intrinsic value, red flags',
  ),
  Agent(
    id: 'market_analyst',
    displayName: 'Market Analyst',
    abbreviation: 'MKT',
    family: AgentFamily.analyst,
    color: AmiColors.hexCyan,
    tagline: 'Charts, indicators, patterns, levels',
  ),
  Agent(
    id: 'news_analyst',
    displayName: 'News Analyst',
    abbreviation: 'NEWS',
    family: AgentFamily.analyst,
    color: AmiColors.hexCyan,
    tagline: 'Macro events, headlines, regulatory news',
  ),
  Agent(
    id: 'social_media_analyst',
    displayName: 'Social Media Analyst',
    abbreviation: 'SOC',
    family: AgentFamily.analyst,
    color: AmiColors.hexCyan,
    tagline: 'Sentiment, crowd mood, retail positioning',
  ),

  // ── Researchers + Managers (purple) ─────────────────────────
  Agent(
    id: 'bull_researcher',
    displayName: 'Bull Researcher',
    abbreviation: 'BULL',
    family: AgentFamily.researcher,
    color: AmiColors.hexPurple,
    tagline: 'Builds the long case',
  ),
  Agent(
    id: 'bear_researcher',
    displayName: 'Bear Researcher',
    abbreviation: 'BEAR',
    family: AgentFamily.researcher,
    color: AmiColors.hexPurple,
    tagline: 'Builds the short / avoid case',
  ),
  Agent(
    id: 'research_manager',
    displayName: 'Research Manager',
    abbreviation: 'RES-M',
    family: AgentFamily.manager,
    color: AmiColors.hexPurple,
    tagline: 'Adjudicates Bull vs Bear, writes synthesis',
  ),

  // ── Risk (amber) ────────────────────────────────────────────
  Agent(
    id: 'aggressive_debator',
    displayName: 'Aggressive Debator',
    abbreviation: 'AGG',
    family: AgentFamily.risk,
    color: AmiColors.hexAmber,
    tagline: 'Argues for risk-on',
  ),
  Agent(
    id: 'conservative_debator',
    displayName: 'Conservative Debator',
    abbreviation: 'CON',
    family: AgentFamily.risk,
    color: AmiColors.hexAmber,
    tagline: 'Argues for capital preservation',
  ),
  Agent(
    id: 'neutral_debator',
    displayName: 'Neutral Debator',
    abbreviation: 'NEU',
    family: AgentFamily.risk,
    color: AmiColors.hexAmber,
    tagline: 'Balances aggressive vs conservative',
  ),

  // ── Execution + Gatekeeper ──────────────────────────────────
  Agent(
    id: 'trader',
    displayName: 'Trader',
    abbreviation: 'TRADE',
    family: AgentFamily.execution,
    color: AmiColors.hexGreen,
    tagline: 'Translates synthesis into a trade idea',
  ),
  Agent(
    id: 'portfolio_manager',
    displayName: 'Portfolio Manager',
    abbreviation: 'PM',
    family: AgentFamily.manager,
    color: AmiColors.hexPurple,
    tagline: 'Final call. Approves or rejects against your mandate.',
  ),

  // ── Concierge (13th, pink) ──────────────────────────────────
  Agent(
    id: 'concierge',
    displayName: 'AMI Concierge',
    abbreviation: 'CNC',
    family: AgentFamily.concierge,
    color: AmiColors.hexPink,
    tagline: 'Personal assistant — lessons, journal, scheduling',
  ),
];


Agent agentById(String id) {
  return kAllAgents.firstWhere((a) => a.id == id,
      orElse: () => kAllAgents.last); // fall back to Concierge if unknown
}
