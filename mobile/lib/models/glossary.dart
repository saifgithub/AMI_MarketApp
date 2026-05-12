/// Glossary — client model for `<Term id="…"/>` references and the
/// standalone in-app dictionary screen. Mirrors
/// backend/app/schemas/glossary.py.
library;

class GlossaryEntry {
  const GlossaryEntry({
    required this.id,
    required this.term,
    required this.definition,
    required this.category,
    required this.seeAlso,
    required this.relatedLessons,
    required this.relatedAgents,
    required this.tags,
  });

  final String id;
  final String term;
  final String definition;
  final String category;
  final List<String> seeAlso;
  final List<String> relatedLessons;
  final List<String> relatedAgents;
  final List<String> tags;

  factory GlossaryEntry.fromJson(Map<String, dynamic> j) {
    return GlossaryEntry(
      id: j['id'] as String,
      term: j['term'] as String,
      definition: j['definition'] as String,
      category: j['category'] as String? ?? 'basics',
      seeAlso: ((j['see_also'] as List?) ?? const []).cast<String>(),
      relatedLessons:
          ((j['related_lessons'] as List?) ?? const []).cast<String>(),
      relatedAgents:
          ((j['related_agents'] as List?) ?? const []).cast<String>(),
      tags: ((j['tags'] as List?) ?? const []).cast<String>(),
    );
  }
}
