import 'package:flutter/material.dart';

/// Observateur de navigation global permettant aux écrans de lecteur vidéo
/// (et autres composants sensibles au cycle de vie de l'affichage)
/// d'être notifiés lorsqu'ils sont recouverts par un autre écran ou modal (RouteAware).
final RouteObserver<ModalRoute<void>> appRouteObserver = RouteObserver<ModalRoute<void>>();
