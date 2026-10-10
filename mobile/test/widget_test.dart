import 'package:flutter_test/flutter_test.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:vidtele_mobile/main.dart';

void main() {
  testWidgets('VidTele app initializes smoke test', (WidgetTester tester) async {
    // Build our app and trigger a frame.
    await tester.pumpWidget(
      const ProviderScope(
        child: VidTeleApp(splashMinDuration: Duration.zero),
      ),
    );
    await tester.pump();

    // Verify that the root VidTeleApp widget is rendered
    expect(find.byType(VidTeleApp), findsOneWidget);
  });
}
