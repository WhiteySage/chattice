# PUBLIC_API — machine-readable index

This file is the thin generated-style index for coding agents. The full
human reference: `docs/public-api.md`; rendered signatures:
`docs/api.md`. Architecture test `tests/test_architecture.py::test_every_public_export_is_importable` pins every package's `__all__`; the canonical entry-point rule lives in `docs/public-api.md`.

- chattice: Dispatcher · Router · F · __version__
- chattice.actions: ActionData (`function=` discriminator binding) · ActionDataDecodeError · ActionDataFilter
- chattice.auth: AuthMode · CredentialsProvider · ServiceAccountCredentialsProvider · UserCredentialsProvider · CHAT_BOT_SCOPE
- chattice.capabilities: ResponseCapabilities · ResponseCapability · OutboundCapabilities · OutboundCapability · PreviewCapabilities · PreviewFeature · PREVIEW_APP_COMMAND_TYPES · CapabilityNotSupported
- chattice.cards: Card · CardHeader · Section · Button (string or ActionData binding) · ButtonList · TextParagraph · Divider · TextInput · SelectionInput · DateTimePicker · Action · OpenLink · Dialog · ActionStatus · ActionStatusCode · Validation · TextInputType · AccessoryWidget · RawWidget
- chattice.client: Bot · MessageReplyOption · ChatAPIError + wrapped error classes · wrap_api_error · CredentialsProvider (compat re-export)
- chattice.dispatcher: Dispatcher (`bot=` contextual binding) · Router · EventObserver · Lifespan · LifespanResource
- chattice.events: Event · MessageEvent (`reply`, lossless read metadata) · CommandEvent · CommandKind · ActionEvent · ActionSource · AddedToSpaceEvent · RemovedFromSpaceEvent · UnknownEvent · ErrorEvent · AppHomeEvent · FormSubmitEvent · WidgetUpdatedEvent · SpaceRef.send · ThreadRef.send · refs · form input values · DialogEventType · TimeZone
- chattice.filters: F · MagicExpression · MagicField · Filter · BaseFilter · FilterLike · FilterValue
- chattice.forms: FormModel · FormDecodeError · FormFilter
- chattice.fsm: State · StatesGroup · FSMContext · FSMStrategy · StorageKey · BaseStorage · MemoryStorage · RedisStorage (lazy) · StateFilter · FSMError · FSMRecord · FSMRecordConflict · FSMRecordStorage · MemoryFSMRecordStorage · RedisFSMRecordStorage (lazy) · BaseStorageFromRecord
- chattice.idempotency: IdempotencyStorage · MemoryIdempotencyStorage · RedisIdempotencyStorage · ClaimResult · new_owner
- chattice.integrations.fastapi: create_chat_router · create_pubsub_router · create_workspace_events_router
- chattice.middleware: Middleware · BaseMiddleware · MiddlewareLike · NextHandler
- chattice.observability: ObservabilityHooks
- chattice.testing: MockBot · EventFactory · FakeChatTransport · assert_card_has_button · assert_card_header · set_state_for
- chattice.transports.http: SYNC_RESPONSE_DEADLINE · HTTPInteractionAdapter · InteractionContext · IncomingRequest · IncomingRequestVerifier · GoogleTokenVerifier · MockVerifier · InteractionResponse · ResponseState · WidgetAutocomplete · RawInteractionResponse · VerificationError · DoubleResponseError
- chattice.transports.pubsub: PubSubPushAdapter · PubSubEnvelopeError · decode_message_data · PubSubPushVerifier · GooglePubSubVerifier · MockPubSubVerifier
- chattice.workspace_events: EventsDispatcher · EventsRouter · WorkspaceEvent · WorkspaceEventType · WorkspaceEventError · parse_workspace_event · parse_workspace_envelope
- chattice.experimental: marker has no direct exports; chattice.experimental.ai is distributed but explicitly unstable and outside the stable API
