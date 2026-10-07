(() => {
  const G = GF;
  G.economy = {
    actor(id, characterId = null) {
      return (
        G.world.npcs.find((a) => a.user_id === id) ||
        G.store.state.characters.find(
          (a) =>
            a.user_id === id &&
            a.character_id === (characterId || G.store.state.activeCharacter),
        )
      );
    },
    transaction(
      sender,
      receiver,
      amount,
      item = null,
      quantity = 0,
      type = "trade_gold",
      metadata = {},
    ) {
      return G.logger.append("transactions", {
        transaction_id: G.id("T"),
        timestamp: G.logger.now(),
        sender_id: sender,
        receiver_id: receiver,
        gold_amount: amount,
        item_id: item,
        quantity,
        market_price: item ? G.world.prices[item] : null,
        trade_price: item && quantity ? amount / quantity : null,
        transaction_type: type,
        metadata,
      });
    },
    transfer(sender, receiver, amount) {
      if (
        !sender ||
        !receiver ||
        sender.user_id === receiver.user_id ||
        !Number.isSafeInteger(amount) ||
        amount <= 0 ||
        sender.gold < amount
      )
        return false;
      sender.gold -= amount;
      receiver.gold += amount;
      sender.sent = (sender.sent || 0) + amount;
      receiver.received = (receiver.received || 0) + amount;
      sender.trades = (sender.trades || 0) + 1;
      receiver.trades = (receiver.trades || 0) + 1;
      const t = this.transaction(sender.user_id, receiver.user_id, amount);
      G.logger.event(sender, "trade_gold", {
        target_user_id: receiver.user_id,
        gold_delta: -amount,
        metadata: { transaction_id: t.transaction_id, direction: "send" },
      });
      G.logger.event(receiver, "trade_gold", {
        target_user_id: sender.user_id,
        gold_delta: amount,
        metadata: { transaction_id: t.transaction_id, direction: "receive" },
      });
      return true;
    },
    shopSell(actor, item, quantity) {
      if (
        !G.items[item] ||
        !Number.isSafeInteger(quantity) ||
        quantity <= 0 ||
        (actor.inventory[item] || 0) < quantity
      )
        return false;
      const amount = Math.round(G.world.prices[item] * 0.8) * quantity;
      actor.inventory[item] -= quantity;
      this.earn(actor, amount);
      if (item === "crystal")
        actor.soldCrystals = (actor.soldCrystals || 0) + quantity;
      const t = this.transaction(
        "SYSTEM_SHOP",
        actor.user_id,
        amount,
        item,
        quantity,
        "shop_sell",
      );
      G.logger.event(actor, "market_sell", {
        item_id: item,
        quantity,
        gold_delta: amount,
        metadata: { transaction_id: t.transaction_id, venue: "shop" },
      });
      return true;
    },
    heal(actor) {
      if (actor.gold < 25 || actor.hp >= 100) return false;
      actor.gold -= 25;
      actor.hp = 100;
      const t = this.transaction(
        actor.user_id,
        "SYSTEM_SHOP",
        25,
        null,
        0,
        "heal",
      );
      G.logger.event(actor, "heal", {
        gold_delta: -25,
        metadata: { transaction_id: t.transaction_id },
      });
      return true;
    },
    earn(actor, amount) {
      actor.gold += amount;
      actor.earned = (actor.earned || 0) + amount;
      const day = G.logger.now().slice(0, 10);
      if (actor.earnedDay !== day) {
        actor.earnedDay = day;
        actor.dailyGold = 0;
      }
      actor.dailyGold = (actor.dailyGold || 0) + amount;
    },
    list(actor, item, quantity, unitPrice, target = null) {
      if (
        !G.items[item] ||
        !Number.isSafeInteger(quantity) ||
        quantity <= 0 ||
        !Number.isSafeInteger(unitPrice) ||
        unitPrice <= 0 ||
        unitPrice > 1000000 ||
        (actor.inventory[item] || 0) < quantity
      )
        return false;
      actor.inventory[item] -= quantity;
      const l = {
        listing_id: G.id("L"),
        seller_id: actor.user_id,
        seller_character_id: actor.character_id,
        item_id: item,
        quantity,
        unit_price: unitPrice,
        target_user_id: target,
        created_at: G.logger.now(),
      };
      G.world.listings.push(l);
      G.logger.event(actor, "market_list", {
        item_id: item,
        quantity,
        metadata: {
          listing_id: l.listing_id,
          unit_price: unitPrice,
          target_user_id: target,
        },
      });
      return l;
    },
    cancel(actor, id) {
      const l = G.world.listings.find((l) => l.listing_id === id);
      if (
        !l ||
        l.seller_id !== actor.user_id ||
        (l.seller_character_id && l.seller_character_id !== actor.character_id)
      )
        return false;
      actor.inventory[l.item_id] += l.quantity;
      G.world.listings = G.world.listings.filter((l) => l !== l);
      G.logger.event(actor, "market_cancel", {
        item_id: l.item_id,
        quantity: l.quantity,
        metadata: { listing_id: id },
      });
      return true;
    },
    buy(buyer, id) {
      const l = G.world.listings.find((l) => l.listing_id === id);
      if (
        !l ||
        l.seller_id === buyer.user_id ||
        (l.target_user_id && l.target_user_id !== buyer.user_id)
      )
        return false;
      const seller = this.actor(l.seller_id, l.seller_character_id),
        amount = l.unit_price * l.quantity;
      if (!seller || buyer.gold < amount) return false;
      buyer.gold -= amount;
      this.earn(seller, amount);
      buyer.inventory[l.item_id] =
        (buyer.inventory[l.item_id] || 0) + l.quantity;
      seller.trades = (seller.trades || 0) + 1;
      buyer.trades = (buyer.trades || 0) + 1;
      if (l.item_id === "crystal")
        seller.soldCrystals = (seller.soldCrystals || 0) + l.quantity;
      const t = this.transaction(
        buyer.user_id,
        seller.user_id,
        amount,
        l.item_id,
        l.quantity,
        "market_trade",
        {
          listing_id: id,
          restricted: Boolean(l.target_user_id),
          buyer_character_id: buyer.character_id,
          seller_character_id: seller.character_id,
        },
      );
      G.logger.event(buyer, "market_buy", {
        target_user_id: seller.user_id,
        item_id: l.item_id,
        quantity: l.quantity,
        gold_delta: -amount,
        metadata: { transaction_id: t.transaction_id },
      });
      G.logger.event(seller, "market_sell", {
        target_user_id: buyer.user_id,
        item_id: l.item_id,
        quantity: l.quantity,
        gold_delta: amount,
        metadata: { transaction_id: t.transaction_id },
      });
      G.world.listings = G.world.listings.filter((x) => x !== l);
      return true;
    },
    update() {
      for (const [id, item] of Object.entries(G.items)) {
        G.world.prices[id] = Math.round(
          item.base_price *
            (1 +
              0.12 *
                Math.sin(
                  G.world.elapsed / 4000 + Object.keys(G.items).indexOf(id),
                )),
        );
      }
    },
  };
})();
