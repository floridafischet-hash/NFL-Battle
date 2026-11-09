export interface RuleSection { title: string; text: string }
export interface RuleChapter { number: number; title: string; summary: string; keywords: string[]; sections: RuleSection[] }

export const RULE_CHAPTERS: RuleChapter[] = [
  { number: 1, title: "Spielfeld", summary: "Maße, Markierungen, Endzonen, Tore und Seitenlinien.", keywords: ["feld", "endzone", "yard", "sideline", "hash marks", "goalpost"], sections: [
    { title: "Abmessungen", text: "Das Spielfeld ist zwischen den Goal Lines 100 Yards lang und 53⅓ Yards breit. Hinter jeder Goal Line liegt eine 10 Yards tiefe Endzone." },
    { title: "Markierungen", text: "Yardlinien, Hash Marks, Seiten- und Endlinien bestimmen Ballposition und Aus. Die Goal Line gehört zur Endzone; Seiten- und Endlinien selbst liegen außerhalb des Feldes." },
    { title: "Tore und Teamzonen", text: "Die Torstangen stehen hinter den Endlinien. Spieler- und Coachingbereiche sind klar begrenzt; unbefugtes Betreten kann bestraft werden." },
  ]},
  { number: 2, title: "Der Ball", summary: "Beschaffenheit, Maße und Bereitstellung des Spielballs.", keywords: ["football", "spielball", "luftdruck", "k-ball"], sections: [
    { title: "Beschaffenheit", text: "NFL-Bälle müssen die vorgeschriebenen Maße, das Gewicht und den Luftdruck erfüllen. Der Referee kontrolliert und verwaltet die zugelassenen Bälle." },
    { title: "Kicking Balls", text: "Für Kick-Spielzüge werden gesondert vorbereitete K-Balls verwendet. Teams dürfen die Oberfläche eines Balls nicht unerlaubt verändern." },
  ]},
  { number: 3, title: "Begriffe und Definitionen", summary: "Die wichtigsten Fachbegriffe des Regelwerks.", keywords: ["down", "snap", "fumble", "runner", "possession", "neutral zone", "line of scrimmage", "touchback", "fair catch"], sections: [
    { title: "Down und Snap", text: "Ein Down ist ein einzelner Spielzug. Er beginnt normalerweise mit dem Snap und endet, sobald der Ball tot ist. Die Line of Scrimmage verläuft durch die vordere Spitze des ruhenden Balls." },
    { title: "Ballbesitz", text: "Possession bedeutet sichere Kontrolle über den Ball. Ein Fumble ist der Verlust eines bereits kontrollierten Balls; ein nicht kontrollierter Vorwärtspass ist dagegen unvollständig." },
    { title: "Tot oder lebendig", text: "Ein Live Ball darf gespielt werden. Ein Dead Ball darf nicht weitergespielt werden. Forward Progress bezeichnet den am weitesten erreichten Punkt eines Ballträgers." },
  ]},
  { number: 4, title: "Spielzeit und Uhr", summary: "Viertel, Spieluhr, Play Clock, Timeouts und Two-Minute Warning.", keywords: ["uhr", "spielzeit", "play clock", "timeout", "two minute warning", "delay of game", "viertel"], sections: [
    { title: "Spieldauer", text: "Ein NFL-Spiel besteht aus vier Vierteln zu je 15 Minuten. Nach dem zweiten Viertel folgt die Halbzeit. Die Spieluhr wird je nach Ausgang eines Spielzugs gestartet oder angehalten." },
    { title: "Play Clock", text: "Die Offense muss den Ball vor Ablauf der Spielzug-Uhr ins Spiel bringen. Je nach Situation stehen üblicherweise 40 oder 25 Sekunden zur Verfügung; ein Verstoß ist Delay of Game." },
    { title: "Timeouts", text: "Jedes Team hat drei Timeouts pro Halbzeit. Bei zwei Minuten Restzeit im zweiten und vierten Viertel gibt es eine automatische Unterbrechung. Besondere Regeln verhindern absichtliche Zeitmanipulation." },
  ]},
  { number: 5, title: "Spieler und Ausrüstung", summary: "Aufstellung, Wechsel, Trikotnummern und erlaubte Ausrüstung.", keywords: ["spieler", "11", "wechsel", "substitution", "ausrüstung", "helm", "trikotnummer"], sections: [
    { title: "Elf Spieler", text: "Pro Team dürfen bei einem Spielzug höchstens elf Spieler auf dem Feld stehen. Zu viele Spieler oder fehlerhafte Wechsel führen zu einer Strafe." },
    { title: "Einwechslungen", text: "Wechselt die Offense Personal, muss die Defense grundsätzlich Gelegenheit zu einem entsprechenden Wechsel erhalten. Täuschende oder verspätete Wechsel sind unzulässig." },
    { title: "Schutzausrüstung", text: "Helm, Schulterpolster, Mundschutz und weitere vorgeschriebene Ausrüstung müssen regelkonform sein. Gefährliche oder veränderte Gegenstände sind verboten." },
  ]},
  { number: 6, title: "Kickoff und Free Kicks", summary: "Kickoff, Landing Zone, Touchback, Safety Kick und Onside Kick.", keywords: ["kickoff", "free kick", "onside kick", "landing zone", "touchback", "safety kick"], sections: [
    { title: "Kickoff", text: "Ein Kickoff eröffnet jede Halbzeit und folgt auf Punkte. Für Aufstellung, Setup Zone und Landing Zone gelten besondere Abstände und Bewegungsregeln." },
    { title: "Landing Zone und Touchback", text: "Landung und Berührung des Balls bestimmen, ob er zurückgetragen wird oder ein Touchback entsteht. Die konkrete Startposition hängt von Art und Ausgang des Kicks ab." },
    { title: "Onside Kick", text: "Das kickende Team darf 2026 zu jeder Spielzeit einen Onside Kick ankündigen. Der Ball muss die vorgeschriebene Distanz erreichen oder zuvor vom Receiving Team berührt werden." },
  ]},
  { number: 7, title: "Ball im Spiel und Downs", summary: "Snap, Formation, vier Versuche, First Down und Dead Ball.", keywords: ["first down", "vier versuche", "4th down", "snap", "formation", "false start", "offside", "dead ball"], sections: [
    { title: "Vier Versuche", text: "Die Offense hat vier Downs, um mindestens zehn Yards zu gewinnen. Erreicht sie die Line to Gain, erhält sie ein neues First Down mit vier weiteren Versuchen." },
    { title: "Vor dem Snap", text: "Mindestens sieben Offensivspieler müssen regelkonform an der Line of Scrimmage stehen. False Start, Offside, Encroachment, Illegal Shift und Illegal Motion betreffen Fehler vor oder beim Snap." },
    { title: "Ende eines Downs", text: "Der Ball wird unter anderem tot, wenn ein Ballträger am Boden ist, ins Aus geht, ein Vorwärtspass unvollständig ist, Punkte erzielt werden oder ein Offizieller abpfeift." },
  ]},
  { number: 8, title: "Pässe und Fumbles", summary: "Vorwärtspass, Catch, Interception, Pass Interference und Ballverlust.", keywords: ["pass", "catch", "interception", "pass interference", "dpi", "opi", "intentional grounding", "fumble", "receiver"], sections: [
    { title: "Vorwärtspass", text: "Pro Down ist nur ein Vorwärtspass erlaubt, und er muss von hinter der Line of Scrimmage geworfen werden. Ein illegaler zweiter oder zu weit vorn geworfener Pass wird bestraft." },
    { title: "Catch und Interception", text: "Für einen Catch muss ein Spieler den Ball kontrollieren, beide Füße oder einen anderen zulässigen Körperteil im Feld haben und den Fangvorgang vollenden. Fängt die Defense, wechselt der Ballbesitz." },
    { title: "Pass Interference", text: "Offense und Defense dürfen die Fangchance eines berechtigten Gegners nicht regelwidrig behindern. Defensive Pass Interference wird grundsätzlich am Ort des Fouls durchgesetzt; Offensive Pass Interference kostet 10 Yards." },
    { title: "Intentional Grounding und Fumble", text: "Wirft ein gefährdeter Passer ohne realistische Fangchance absichtlich weg, kann Intentional Grounding vorliegen. Verliert ein Spieler nach gesichertem Ballbesitz die Kontrolle, ist der freie Ball ein Fumble." },
  ]},
  { number: 9, title: "Punts und Field Goals", summary: "Scrimmage Kicks, Punt, geblockte Kicks und Ballberührung.", keywords: ["punt", "field goal", "scrimmage kick", "blocked kick", "kicker", "holder"], sections: [
    { title: "Punt", text: "Beim Punt gibt die Offense den Ball meist im vierten Versuch freiwillig ab und versucht, die gegnerische Startposition nach hinten zu verlagern." },
    { title: "Field-Goal-Versuch", text: "Ein Field Goal ist erfolgreich, wenn der gekickte Ball zwischen den Pfosten und über die Querlatte fliegt. Geblockte oder kurze Versuche bleiben je nach Situation spielbar." },
    { title: "Schutz von Kicker und Holder", text: "Kicker und Holder genießen besonderen Schutz. Running into the Kicker und Roughing the Kicker werden unterschiedlich streng geahndet." },
  ]},
  { number: 10, title: "Fair Catch und Kickfang", summary: "Ungestörte Fangchance, Fair-Catch-Signal und Schutz des Returners.", keywords: ["fair catch", "returner", "kick catch interference", "fangsignal"], sections: [
    { title: "Fangchance", text: "Ein Returner muss eine ungehinderte Gelegenheit erhalten, einen fliegenden Kick zu fangen. Zu früher Kontakt ist Kick Catch Interference." },
    { title: "Fair Catch", text: "Nach einem gültigen Fair-Catch-Signal darf der Fänger nicht getackelt werden, den Ball aber auch nicht zurücktragen. Ungültige Signale können die Rückgabe ebenfalls beenden." },
  ]},
  { number: 11, title: "Punkte", summary: "Touchdown, Extra Point, Two-Point Conversion, Field Goal und Safety.", keywords: ["punkte", "touchdown", "extra point", "pat", "two point conversion", "field goal", "safety", "6 punkte", "3 punkte", "2 punkte"], sections: [
    { title: "Touchdown – 6 Punkte", text: "Ein Touchdown zählt, wenn ein Ballträger mit kontrolliertem Ball die gegnerische Goal Line durchbricht oder ein berechtigter Receiver einen Pass in der Endzone fängt." },
    { title: "Try nach dem Touchdown", text: "Ein erfolgreicher Kick bringt einen Punkt. Ein Lauf oder Pass in die Endzone bringt zwei Punkte. Auch die Defense kann einen Try-Ball für zwei Punkte zurücktragen." },
    { title: "Field Goal und Safety", text: "Ein Field Goal zählt drei Punkte. Ein Safety bringt der Defense zwei Punkte, wenn die Offense den Ball mit eigenem Impuls in der eigenen Endzone tot werden lässt oder dort ein entsprechendes Foul begeht." },
  ]},
  { number: 12, title: "Spielerverhalten und Fouls", summary: "Blocks, Holding, Tackles, persönliche Fouls und Unsportlichkeit.", keywords: ["holding", "block", "facemask", "horse collar", "hip drop", "roughing", "taunting", "helmet", "personal foul", "unsportsmanlike"], sections: [
    { title: "Holding und unerlaubte Blocks", text: "Offensive Holding kostet typischerweise 10 Yards, Defensive Holding 5 Yards und ein automatisches First Down. Blocks in den Rücken, Chop Blocks, Clipping und bestimmte tiefe Blocks sind verboten." },
    { title: "Gefährlicher Kontakt", text: "Verboten sind unter anderem Facemask, Horse-Collar- und Hip-Drop-Tackle, Roughing the Passer, unerlaubter Helmeinsatz und Kontakt gegen einen schutzlosen Spieler. Viele dieser Fouls kosten 15 Yards." },
    { title: "Unsportliches Verhalten", text: "Taunting, Beleidigungen, Schläge und Kontakt mit Offiziellen können 15 Yards, Disqualifikation und weitere Ligamaßnahmen auslösen." },
  ]},
  { number: 13, title: "Verhalten an der Seitenlinie", summary: "Regeln für Coaches, Ersatzspieler und sonstige Nicht-Spieler.", keywords: ["coach", "sideline", "bank", "non-player", "seitenlinie"], sections: [
    { title: "Teamzone", text: "Coaches, Ersatzspieler und Personal müssen in den vorgesehenen Bereichen bleiben und dürfen Offizielle oder den Spielablauf nicht behindern." },
    { title: "Unsportliche Handlungen", text: "Beleidigungen, unerlaubtes Betreten des Feldes, Eingriffe in einen Spielzug und außergewöhnlich unfaire Handlungen werden gegen das Team bestraft." },
  ]},
  { number: 14, title: "Durchsetzung von Strafen", summary: "Penalty Enforcement, Straforte, automatische First Downs und doppelte Fouls.", keywords: ["strafe", "penalty", "yards", "spot foul", "automatic first down", "loss of down", "double foul", "offsetting"], sections: [
    { title: "Annahme oder Ablehnung", text: "Das benachteiligte Team darf eine Strafe meist annehmen oder ablehnen. Manche Fouls haben zusätzliche Folgen wie Loss of Down oder Automatic First Down." },
    { title: "Ort der Durchsetzung", text: "Je nach Foul gelten Previous Spot, Spot of the Foul, End of the Run, Succeeding Spot oder besondere Regeln. Nahe der Goal Line kann Half the Distance gelten." },
    { title: "Fouls beider Teams", text: "Bei Double Fouls können sich Strafen aufheben und der Down wird wiederholt. Besitzwechsel und persönliche Fouls führen zu Ausnahmen." },
  ]},
  { number: 15, title: "Videobeweis", summary: "Replay Review, Challenges, Booth Review und überprüfbare Entscheidungen.", keywords: ["replay", "challenge", "videobeweis", "review", "booth", "rote flagge"], sections: [
    { title: "Coach's Challenge", text: "Ein Head Coach kann bestimmte Entscheidungen mit der roten Flagge überprüfen lassen, wenn ihm ein Timeout zur Verfügung steht. Eine erfolglose Challenge kostet ein Timeout." },
    { title: "Automatische Reviews", text: "Scoring Plays, Turnovers und bestimmte Situationen in den letzten zwei Minuten werden zentral eingeleitet. Nicht jede Ermessensentscheidung und nicht jedes Foul ist überprüfbar." },
    { title: "Eindeutiger Beweis", text: "Eine Entscheidung wird nur geändert, wenn die Wiederholung klare und überzeugende Belege liefert. Andernfalls bleibt die Entscheidung auf dem Feld bestehen." },
  ]},
  { number: 16, title: "Overtime", summary: "Verlängerung in Regular Season und Playoffs.", keywords: ["overtime", "verlängerung", "unentschieden", "sudden death", "münzwurf", "playoffs"], sections: [
    { title: "Grundprinzip", text: "Die Overtime beginnt mit einem Münzwurf. Beide Teams sollen grundsätzlich Gelegenheit zu Ballbesitz erhalten; danach entscheidet der nächste Punktgewinn, sofern noch Gleichstand besteht." },
    { title: "Regular Season", text: "In der regulären Saison ist die Overtime zeitlich begrenzt. Bleibt es nach Ablauf der Verlängerung unentschieden, endet das Spiel als Tie." },
    { title: "Playoffs", text: "Playoffspiele müssen einen Sieger haben. Ist nach einer Overtime kein Sieger ermittelt, folgen weitere Perioden bis zur Entscheidung." },
  ]},
  { number: 17, title: "Notfälle und unfaire Handlungen", summary: "Außergewöhnliche Situationen und Befugnisse der Spielleitung.", keywords: ["notfall", "emergency", "unfair act", "palpably unfair", "spielabbruch"], sections: [
    { title: "Notfälle", text: "Bei Wetter, Sicherheitsproblemen, technischen Ausfällen oder anderen Notfällen kann die Ligaleitung ein Spiel unterbrechen, verlegen oder fortsetzen." },
    { title: "Außergewöhnlich unfair", text: "Bei einer klar unfairen Handlung, die nicht angemessen abgedeckt ist, darf der Referee eine passende Strafe bis hin zur Punktevergabe anwenden." },
  ]},
  { number: 18, title: "Teamkapitäne", summary: "Aufgaben der Captains bei Münzwurf und Kommunikation.", keywords: ["captain", "kapitän", "coin toss", "münzwurf", "wahlrecht"], sections: [
    { title: "Münzwurf", text: "Die Captains vertreten ihr Team beim Coin Toss und erklären die Wahl zu Ballbesitz, Spielfeldseite oder Aufschub der Entscheidung." },
    { title: "Kommunikation", text: "Captains können Entscheidungen zu angebotenen Strafen mitteilen. Coaches dürfen diese Verantwortung nach den vorgesehenen Abläufen übernehmen." },
  ]},
  { number: 19, title: "Offizielle", summary: "Schiedsrichterteam, Zuständigkeiten und Unterstützung durch die Liga.", keywords: ["referee", "official", "schiedsrichter", "umpire", "down judge", "line judge", "disqualifikation"], sections: [
    { title: "Schiedsrichterteam", text: "Die Crew überwacht Snap, Ballposition, Zeit, Pässe, Kicks, Linien und Spielerverhalten. Der Referee verkündet Entscheidungen und hat die Gesamtaufsicht auf dem Feld." },
    { title: "Liga-Unterstützung", text: "NFL-Officiating-Personal darf die Crew in festgelegten Situationen beraten. Seit 2026 umfasst dies auch mögliche Disqualifikationen wegen eklatanter Handlungen, selbst wenn sie zunächst nicht geflaggt wurden." },
  ]},
];
