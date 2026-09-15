def auto_encoder(load_weights=True, weights_file=None):
    filters = [45, 33, 16, hidden_units]  # Adjust filters as needed
    init = "uniform"
    activation = "relu"
    input_shape = (input_dim,)
    l2_reg = tf.keras.regularizers.L1L2(l1=0.01, l2=0.01)  # L2 regularization

    input = tf.keras.layers.Input(shape=input_shape)
    x = input

    # Encoder
    for i in range(len(filters)):
        x = tf.keras.layers.Dense(
            filters[i],
            activation=activation,
            kernel_initializer=init,
            kernel_regularizer=l2_reg,
        )(x)
        x = tf.keras.layers.Dropout(0.1)(x)
        x = tf.keras.layers.BatchNormalization()(x)

    h = x  # bottleneck layer

    # Decoder
    for i in range(len(filters) - 1, 0, -1):
        x = tf.keras.layers.Dense(
            filters[i],
            activation=activation,
            kernel_initializer=init,
            kernel_regularizer=l2_reg,
        )(x)
        x = tf.keras.layers.Dropout(0.1)(x)
        x = tf.keras.layers.BatchNormalization()(x)

    y = tf.keras.layers.Dense(
        input_shape[0], kernel_initializer=init, kernel_regularizer=l2_reg
    )(x)

    model = tf.keras.Model(inputs=input, outputs=y)

    if load_weights and weights_file and os.path.exists(weights_file):
        model.load_weights(weights_file)
        print("autoencoder: weights were loaded")
    else:
        print("autoencoder: weights file not found, training from scratch")

    return model
